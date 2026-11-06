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

*Amended 5 Nov 2026 by D53: an uncorrected item whose band is clearly trivial is not
accumulated. Everything else below stands.*

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

## D47 · Stage 6, part 1: the frontend foundation and the engagement list — 5 Nov 2026

The first part of Stage 6 builds what every screen stands on, and one screen. Nothing in
the backend changed: no route, model, migration or rule.

- **Routing without a dependency.** `frontend/src/router.ts` is a hash router of some forty
  lines, the Binder's convention. Two addresses exist: `#/` (the engagements) and
  `#/engagements/{id}` (one engagement's schedule). An address it does not know shows the
  engagement list. No router package was added.
- **The API client is a typed mirror, and a refusal is shown in the backend's words.**
  `frontend/src/api.ts` declares the shapes the backend answers and one `ApiError`. Its
  message is the backend's `detail`; a validation failure is read as "field: message"; a
  `pending_decision` is carried through and named on the screen; a backend that cannot be
  reached says so and names port 8003. The client decides nothing.
- **Figures are never passed through floating point.** `frontend/src/format.ts` formats the
  API's decimal strings as text: Indian digit grouping, the rupee sign, a negative sign
  before the sign of the currency, zeros padded and digits never rounded away. A percentage
  is computed exactly with integers, rounded half up, at presentation only (D16).
- **One of three states, always.** `useResource` holds a load as loading, ready or failed,
  and `components/states.tsx` gives each its appearance: a polite status, an empty state
  with its explanation, an alert with the failing request and a retry.
- **The engagement list** reads `GET /api/engagements` and shows, for each engagement, its
  label, whether it is linked to the Financial Spine and pinned to a version, its number of
  misstatements, whether thresholds are set, who created it and when. The label opens the
  schedule address.
- **The schedule page is a header only.** It reads `GET /api/engagements/{id}` and shows
  what the backend says about the engagement, including the verified state of the Spine
  link. Where the schedule will be it says that the schedule is not built. No row, total
  or filter is shown in any made-up form.
- **The frontend's test fixtures are the API's real answers.** The screens are tested
  against JSON in `frontend/tests/fixtures`. `backend/tests/test_frontend_fixtures.py`
  produces those files by driving the real application, and fails when a committed fixture
  no longer equals what the API answers (identifiers and timestamps masked). A fixture
  written by hand could describe a backend that does not exist; these cannot drift
  unnoticed. The engagements in them are labelled as test engagements and name no client.

**Not built in this part:** the schedule's rows, running totals and filters; the
misstatement detail screen; the evaluation screen; any screen that writes. The list offers
no way to create an engagement, because the spec names three screens and that is not one of
them; whether to add one is a question for the review, not a decision taken here.

## D48 · Stage 6, part 2: the schedule of misstatements — 5 Nov 2026

The schedule address now shows the schedule (spec sections 6.1 and 10.1), replacing the
header-only page of D47. Nothing in the backend changed: no route, model, migration or rule.
The only backend file touched is the test that produces the frontend's fixtures.

- **Three reads, no new route.** The page asks for the engagement, its misstatements
  (`GET /api/engagements/{id}/misstatements`) and its evaluation
  (`GET /api/engagements/{id}/evaluation`) together. If any one fails, nothing partial is
  shown: a schedule without its totals, or totals without the rows, would mislead.
- **The ten columns of section 6.1.** Reference, type, description, Dr/Cr lines, effect on
  profit before tax, effect on net assets, band, state, working paper reference, who raised
  it. The lines are the Spine's as the API sends them; the effects and the band are the
  backend's. An effect the backend could not determine is shown as not available with the
  backend's reason, never as nil. A classification-only item, a judgemental range that
  crosses PM and a state that disagrees with the Spine are each said in words.
- **The running totals are the evaluation's aggregate.** Gross and net, profit before tax
  and net assets, in rupees, exactly as `aggregate` gives them. The screen adds nothing up.
  It says what was counted and what was not, names the projected items with the totals
  without them (spec section 3.2), flags totals the backend marks incomplete, and gives the
  backend's own description of how the aggregate is computed.
- **The percentages are presentation (D16).** Each total as a percentage of CTT, PM and OM
  is computed on the screen, exactly, with integers, rounded half up to one decimal place;
  the size of the figure is what is compared, so a net figure below zero reads as a positive
  percentage. No API gives these percentages, and D16 already places them at presentation.
  With no thresholds set there is no percentage, and none is invented.
- **Filters choose rows, and only rows.** Band, type and state filter the list already
  loaded; the band filter has a fourth value for items the backend could not band. The
  totals stay the backend's aggregate of the whole engagement and are not recomputed for
  the rows shown: summing a filtered subset on the screen would be a second aggregation
  rule, and the screen says that the filters do not change the totals. This is this
  module's reading of "running totals ... always visible" (spec section 10.1).
- **Always visible.** On a screen of tablet width or more the totals stay in view while
  the schedule scrolls beneath them. On a phone they sit at the top and scroll with the
  page, since a pinned panel would leave no room for the schedule.
- **No sideways scrolling.** From 1280 pixels the schedule is a table. Below that each
  misstatement is a block with every value labelled by its column, the same markup laid out
  differently.
- **The detail address exists and shows a header only.** `#/misstatements/{id}` reads
  `GET /api/misstatements/{id}` and shows the reference, type, state, band and description,
  with a way back to the schedule. It says that the detail is not built.
- **Fixtures.** The fixture test now also drives one engagement through every type, every
  state and every band, an engagement with nothing raised, and the first again with the
  Spine unreachable, and writes the API's answers for each. All of it runs in the test
  transaction and is rolled back.

**Not built in this part:** the misstatement detail (lines, effects, state trail, working
paper); the evaluation screen with the gates and the conclusion; any screen that writes. No
form to create an engagement or to raise a misstatement was added, by instruction.

**Assumptions to confirm:** that the running totals are the aggregate of the uncorrected
misstatements of the whole engagement (the backend's F3 reading), unaffected by the
filters; that one decimal place is the right precision for the percentages; that the gate
status belongs on the evaluation screen and not above the schedule.

## D49 · Stage 6, part 3: the misstatement detail and its moves — 5 Nov 2026

The detail address now shows the whole misstatement (spec sections 6.1 and 10.2) and is
the first screen that writes: it sends the moves of the state machine. Nothing in the
backend changed: no route, model, migration or rule. The only backend file touched is the
test that produces the frontend's fixtures.

- **One read, one write, both existing.** The page reads `GET /api/misstatements/{id}` and
  sends `POST /api/misstatements/{id}/transitions`. It asks for nothing else.
- **Identification.** Reference, type, description, state, band with the threshold version
  it was computed against, working paper reference, where it was raised from, who raised it
  and when. A judgemental item shows the auditor's range, and says when the backend finds
  that the range crosses PM; a projected item names its sample and projection basis.
- **Dr/Cr lines with their classification.** Each line as the Spine holds it: ledger, the
  group it sits under, the Schedule III head, the statement and the section the effects are
  computed on, debit or credit. The Spine's adjustment is shown beside them: status, kind,
  reference, gross size, who proposed and decided it and the decision note. The screen adds
  nothing up.
- **Effects, each with the backend's explanation.** The effect on profit before tax and on
  net assets, each with its own band and with `profit_basis` and `net_assets_basis` as the
  backend wrote them; the effect on each caption; the band with `band_basis`. An effect the
  backend could not determine is disclosed with its reason and is never shown as nil. When
  the Spine now classifies a ledger differently from the classification recorded at raising
  (D32), the page says which ledger, how, and what the effects would be on the current
  classification; the effects themselves do not change.
- **The versions are the history.** Every move added a version and none is ever changed
  (D9, D41), so the state trail is the list of versions: the state recorded, who recorded
  it, when, and the reason for a refusal or a withdrawal. A state the Spine disagrees with
  is flagged with the backend's explanation.
- **Which moves are offered is a mirror of the diagram; whether a move happens is the
  backend's.** The API does not say which moves are open from a state, so the screen holds
  the diagram of spec section 3.3 (`NEXT_STATES` in `labels.ts`: raised to communicated;
  communicated to corrected, refused or withdrawn; nothing from a final state) to decide
  which buttons to show. That is all it decides. The backend checks every move, and a
  refusal is shown in its words, so a screen that offered a wrong move could not make it.
- **A move is chosen, then confirmed.** Every move is irreversible, so choosing one opens
  what it will do and a second control confirms it. A refusal and a withdrawal require a
  reason that is not blank before they can be confirmed, as the backend requires; the
  backend's limit of 1,500 characters is mirrored on the field. The reason goes out without
  the spaces around it.
- **Once.** While a move is processing every control is disabled and says so, and a guard
  held outside the render makes a second confirmation in the same instant send nothing.
  This is tested, and the test was checked: with the guard taken out, it fails.
- **After a move.** The backend's answer to a move is the misstatement as it then stands,
  with every version, so the page shows that answer at once rather than reading again. The
  schedule is read afresh every time it is opened, so it shows the move too. What the move
  asked of the Spine, and the note the Spine recorded, are reported.
- **Nothing can be edited.** No field of a recorded version is offered for change. The only
  input on the page is the reason of a move being confirmed.
- **Fixtures.** The fixture test now also takes one misstatement through raised,
  communicated and corrected, a judgemental one to refused and a projected one to
  withdrawn, and writes the API's answer at each step: every read, every move, and every
  refusal met on the way (a move the diagram does not draw, a refusal with no reason, a
  blank reason, a move from a final state, the Spine unreachable). Two different
  identities act, so the history shows who did what. All of it is rolled back.

**Not built in this part:** the qualitative checklist of spec section 10.2, which is Pass 2
(D19) and has no backend; the evaluation screen with the gates and the conclusion; any way
to create or edit a misstatement.

**Assumptions to confirm:** that any signed-in identity may make a move from the screen,
which is what the backend allows today (authorisation is not enforced: B9); that asking for
a confirmation before every move, not only the three final ones, is wanted; the wording of
what each move does, which restates spec section 3.3 and D41.

## D50 · Stage 6, part 4: the evaluation screen — 5 Nov 2026

The third screen of spec section 10: `#/engagements/{id}/evaluation`, reached from the
schedule and leading back to it. Nothing in the backend changed: no route, model, migration
or rule. The only backend file touched is the test that produces the frontend's fixtures.

- **Six reads, two writes, all existing.** The page reads the engagement, the evaluation,
  the runs, the conclusions and the two gates other modules read
  (`/gates/opinion`, `/gates/sign-off`). If any read fails nothing partial is shown. It
  sends `POST .../evaluation/runs` and `POST .../evaluation/strategy-responses`, the two
  evaluation writes the backend opens to any signed-in identity.
- **The aggregate.** Gross and net, profit before tax and net assets, with and without the
  projected items, and the gross contribution of factual, judgemental and projected items,
  exactly as the evaluation gives them. The screen adds nothing up. It names what was
  counted and what was not, and flags an aggregate the backend marks incomplete.
- **Against the three lines.** CTT, PM and OM with the threshold version, and each figure
  as a percentage of each line (presentation, D16, exact, as on the schedule). **Whether a
  figure is at or above a line is not decided on the screen.** The soft gate names the
  measures at or above PM and the hard gate those at or above OM (`fires_on`); the table
  marks exactly those. A test gives the screen figures at the line with gates that name
  nothing, and nothing is marked. No gate exists at CTT, which is a line for single items,
  so no mark is shown there.
- **The gates.** The hard gate and the soft gate with their line, highest measure, the
  measures they fire on, whether they depend on the projected items (B8), the firm's
  setting for the soft gate and the state of the partner's acknowledgement; the opinion
  gate and the sign-off gate as other modules read them, open, blocked or undetermined,
  with every reason the backend gives; and the items that block on their own. Every status
  and reason is the backend's, and its own descriptions of each gate are shown.
- **A status this screen does not know is never good news.** The status words live in one
  place (`labels.ts`); a code with no word is shown as it was sent and flagged.
- **Runs.** The history lists every evaluation row, newest first, with its four aggregates,
  threshold version, who recorded it and when. Only the latest row can still describe the
  evaluation, and the backend says whether it does (`latest_run`: current or stale, with
  the reason); an earlier row is marked as earlier. Any row can be inspected: its
  thresholds, its figures without the projected items, the gates and the sign-off decision
  as they were, and each misstatement's state, type and band at that moment, exactly as
  recorded.
- **Recording a run.** The request carries one thing, that materiality was reassessed
  first (SA 450 paragraph 10), and a person must state it each time: the control is unticked
  again after every run. No figure is sent. The backend refuses a run it cannot compute in
  full, and its reason is shown. After a run the six reads are made again and the screen is
  not blanked while they are (`useResource.refresh`).
- **The strategy prompt.** Shown as the backend evaluates it: not configured (B5), or its
  line, the measures at it, and whether it has been answered on the current figures. The
  answer is offered only when the backend says one is needed, and is what the specification
  names: whether the strategy and plan were revised, "recorded either way", with an
  optional note. The choice has no default.
- **The conclusion is shown, not recorded.** The latest conclusion with its determination,
  words, basis, figures, threshold version, who concluded and which run was reviewed;
  whether it is current or stale, for the backend's reason; the earlier conclusions; and,
  for each kind of conclusion, whether the backend's gates would refuse it now and why.
- **Partner-only actions are never sent.** The soft-gate acknowledgement and the
  conclusion are reserved to the engagement partner (D39, D45). The screen has no control
  for either and the API client has no function for either, which a test asserts. Where the
  backend reports that no trusted role claim is configured, each is shown as unavailable
  with the backend's explanation; where one is configured, each is shown as reserved to the
  partner and not offered on this screen.
- **Once.** Both writes share one guard (`useSubmit`): while a write is in flight every
  control is disabled and a second confirmation sends nothing. Tested, and the tests were
  checked by removing the guard, which fails them.
- **Fixtures.** The fixture test now captures, for each scenario, everything the screen
  reads in one file: nothing raised; no gate firing, before a run, after it, stale, and
  with two runs; the Spine unreachable; the strategy prompt before and after its answer;
  the aggregate at PM; at OM only with a projected item; an item above PM; and, with the
  app run behind a trusted proxy the way production is, a conclusion recorded by a partner,
  gone stale, and replaced. An event's sequence number is now masked in the comparison
  with the identifiers and times, since the database issues a new one on every run.

**Not built in this part:** the forms for the two partner-only writes; the prior-period
carry-forward of spec section 10.3 (current and cumulative), which is Pass 2 and has no
backend; any way to set or revise thresholds.

**Assumptions to confirm:** that the conclusion and the soft-gate acknowledgement are to
be shown and not recorded from this screen in this part; that no mark is wanted at CTT;
that the marks should follow the gates' `fires_on`, which is tested on the figures that
include the projected items; that a person should have to state the reassessment of
materiality afresh for every run.

## D51 · Stage 6, part 5: the screens reviewed together — 5 Nov 2026

A review of the whole specification against the four screens and the API, recorded in full
in `docs/CLOSURE_REVIEW.md` section 10. Nothing in the backend changed.

- **One path, on answers that belong together.** The fixture test now also writes the
  engagement list and the evaluation as they stood for the engagement whose schedule and
  misstatement were already captured, so a single test walks list, schedule, detail, back,
  evaluation and back by the links on the screens, on one engagement's real answers.
- **No dead link, by test.** A test starts at the engagement list, follows every link on
  every screen it reaches, and requires each address to be one the router knows and each
  screen to load without a failure. It finds the four addresses and no other.
- **Amounts are traced, not trusted.** A test reads every rupee amount off the schedule,
  the detail and the evaluation, with every run opened, takes the formatting off again,
  and requires each to be a decimal the backend sent, digit for digit, with exactly two
  decimal places. The largest amount the money domain can hold is formatted without losing
  a paisa, where a float would. The source contains no floating-point arithmetic.
- **One defect fixed.** The dash shown for the side a Dr/Cr line does not carry was too
  pale to read (2.6 to 1 against white); it now meets 4.5 to 1. Found by computing the
  contrast of every piece of text on every screen in a browser; nothing else fell short.
- **Checked in a browser** at 1280, 768 and 375 pixels with the captured answers standing
  in for the API: no screen scrolls sideways; a pass through every screen, an unknown
  address, a filter, an opened run and a chosen move logs no error or warning; no write
  was sent.
- **Partner-only writes.** Confirmed by test that no control and no client function exists
  for the acknowledgement or the conclusion. The backend's own refusal of a non-partner
  (403, captured) is the enforcement; the screens add none and remove none.

**What the review found that Stage 6 does not do**, each now a row in the register: no
screen for thresholds (S1); none to create an engagement or raise a misstatement (S2); the
conclusion and the acknowledgement shown and not recorded (S3); and, outside the spec, one
page title for every screen, focus not moved on navigation, and no favicon (S12). Stage 6
uses 13 of the API's 26 routes.

**Verdict.** The three screens of spec section 10 exist and are tested, without the Pass 2
parts. Stage 6 is complete against the instructions it was built to. It is not complete
against the spec's words in one respect that is Pass 1: "the conclusion field" is shown and
cannot be filled in from the screen (S3). Nothing has been seen on live data (V9, V10).

## D52 · Closing Stage 6: the remaining screens, the partner's forms, and a live preview — 5 Nov 2026

One remediation of S1 to S12 and V9 to V11, recorded item by item in
`docs/CLOSURE_REVIEW.md` section 11. Nothing in the backend's source or migrations changed.

- **Five screens were added, each over routes that already existed.** New engagement;
  record a misstatement; thresholds; Financial Spine (the link and the reconciliation);
  events. Every engagement screen carries the same tabs, so each is reached from every
  other. The screens now use 24 of the API's 26 routes.
- **A form sends what a person declared, as the text that was typed.** Amounts and the
  fraction go out as strings. The recording form does not add up debits and credits: the
  backend checks the balance (acceptance 1) and its refusal is shown in its own words.
- **Thresholds are never edited.** The form is the same for the first version and for a
  revision; a revision is how a reassessment of materiality is recorded, and the screen
  shows the recompute the backend wrote (acceptance 2). The clearly-trivial amount is the
  backend's and is not previewed.
- **No ledger picker.** The API has no route that lists the Spine's ledgers or heads, so a
  line is entered by its import line number, or by name, groups and head. No route was
  added: that is a decision (register S13).
- **The partner's two forms are offered where the backend says a partner can be named.**
  `authorisation.partner_actions.available` decides whether a form appears; the backend
  decides whether the person sending it is the partner, and its 403 is shown as sent. A
  conclusion the backend reports its gates would refuse cannot be chosen. The run reviewed
  is the latest one, and only while the backend calls it current. The client sends no
  role, no user and no figure, which a test asserts. This reverses D50's "shown, not
  recorded" and the two tests that pinned it: both were re-aimed, not deleted.
- **"Always visible" now means every width (S7).** The running totals are pinned on a
  phone too, set smaller so that they fit; an amount too long for the screen scrolls inside
  the panel, never the page.
- **Accessibility (S12).** A title per screen; focus moved to the content when the screen
  changes, not on the first load; a control that skips to the content; a favicon. Checked
  with real key presses and by computing the contrast of every piece of text.
- **What the specification does not decide was left as it was.** Whether totals follow
  filters (S5), the precision of a percentage (S6), a mark at CTT (S8), a confirmation
  before each move (S9), who may make the ordinary writes (S10). Each keeps the safe
  behaviour and names who decides.
- **The eight untested branches (V11) are tested on real answers.** The fixture test moves
  the Spine double into each situation and captures what the backend then says.
- **A preview that keeps nothing (V9, V10).** `backend/tests/preview_server.py` serves the
  real application over `oak_misstatements_test` inside one transaction that is never
  committed, with the Spine double, the development identity and the built frontend on one
  port, one request at a time. It exists because the alternative asked for, a separate
  preview database, is not available without a superuser and a change to the settings
  guard that refuses any database but the two. It was used once, stopped, and the test
  database was read afterwards: no row in any table.
- **No partner was simulated.** One request drafted for the live check carried a role
  header; it was refused before it ran and removed. The partner's writes were verified
  live only as refusals.

**Not built:** a ledger picker (S13); anything of Pass 2.

**Stage 6 is not declared complete.** The conclusion and the acknowledgement cannot be made
end to end until a partner can be named (V12); the live Spine and the main database are
untouched (V5, V6); S5, S6, S8, S9, S10 and S13 wait on people.

*As at D52. Superseded: since D55 and section 13 of `docs/CLOSURE_REVIEW.md` the position
is stated as "the Pass 1 implementation is complete; production acceptance is pending".
The items named here have since been closed or consolidated; the register lists the 18
that are open.*

## D53 · Clearly trivial items are not accumulated — 5 Nov 2026 (S14)

**Why.** Spec section 2, the row for SA 450 paragraph 5, says "everything above it
accumulates"; section 4 says of the clearly trivial band "Below it, not accumulated". D38
summed every uncorrected item whatever its band, so a clearly trivial item was inside the
aggregate, the gates, the runs and the conclusions (register S14). Built on the instruction
of 5 November 2026 to apply the specification's wording. It is not a decision of the CA:
the eight questions of S14 stay open, and each has an interim treatment below.

*As at D53. Interim treatment 2 below no longer describes the module: D57 accumulates
clearly trivial items once together they reach the threshold. A ninth question was added
by D55 and answered in code by D56. Of the nine, only question 2 is still open, narrowed
to how "in aggregate" is measured.*

**The rule.** `core/gates.py`, `accumulates()`: an uncorrected, resolved item is summed
unless its band is clearly trivial. `aggregate()` sums only those, and names the others in
`Aggregate.not_accumulated`. The evaluation's `aggregate.not_accumulated` and a run's
`detail.not_accumulated` carry the references; `AGGREGATE_BASIS` says so in words. Nothing
else changed: no model, no migration, no route, no database rule. The database's hard-gate
check reads the stored aggregates and needs no change.

**What is kept exactly as it was.**

- Corrected and withdrawn items are excluded by their state (F3) and are not named as
  clearly trivial.
- A refused item counts (F3), a projected item counts (B8 interim) and a judgemental item
  counts on its point estimate (D14), each unless its band is clearly trivial.
- An unresolved item has no band, is never treated as clearly trivial (D33), and leaves
  the aggregate incomplete and the gates indeterminate.
- A classification-only item bands clearly trivial only because both effects are nil. It
  stays listed at nil in `counted` and `classification_only` (B2), and is not named in
  `not_accumulated`. No figure depends on this.
- With no thresholds there is no band: nothing is left out, and no gate is evaluated.
- The individual tests (individually significant; at or above OM alone) never used the
  aggregate and are unchanged.
- Every misstatement stays in the schedule and in the evaluation's list of items, with its
  band and its own amounts (spec section 10.1).

**Interim treatments of the CA's questions** (S14; none is a decision):

1. *Item or measure.* The band is the item's, the higher of its two effects' bands (D33,
   itself an assumption). An item is in the aggregate with both effects or with neither.
2. *Trivial in aggregate.* The spec's wording as written: items left out are compared with
   no line, however many there are. They are named; no total of them is shown and no
   warning is raised, because the spec asks for neither.
3. *Classification-only.* Listed at nil, as before.
4. *The schedule.* Every item stays listed.
5. *Communicated or refused and clearly trivial.* Left out like any other clearly trivial
   item; the state changes nothing. The TCWG and representation lists are Pass 2.
6. *Projected and clearly trivial.* Left out like a factual one. B8 is otherwise untouched.
7. *Escalated below CTT* (F5). Not built: escalation is Pass 2. When it is built the rule
   needs an exception, which `accumulates()` is the one place for.
8. *A revised CTT.* Bands are computed on read (D33), so a revision moves items into and
   out of the aggregate at once. Tested.

**Consistency, checked by test.**

- *Gates.* The hard gate, the soft gate, the PM gate set to hard and the strategy trigger
  read the one aggregate. Twenty-one items of 12,000 fire nothing; one item at PM fires.
- *Runs.* A run stores the figures and the labels of every item, clearly trivial ones
  included. Raising a clearly trivial item moves no figure and still makes the latest run
  stale, because the list of items is no longer the list.
- *Acknowledgements and strategy answers.* Each is tied to the figures (D39, D45). A
  clearly trivial item moves none, so the acknowledgement or answer stands.
- *Conclusions.* The run reviewed must still describe the evaluation, so a clearly trivial
  item raised after the review refuses the conclusion until a new run is reviewed; the
  figures on the new row are the reviewed ones.
- *Earlier records.* Nothing was added to `figures()`, so a run recorded before this
  change is stale only if it had counted a clearly trivial amount. Neither database held a
  run when the change was made.

**The screens.** The running totals and the aggregate panel say how many misstatements are
accumulated, name those that are "clearly trivial, not accumulated", and say that such an
item stays in the schedule and is in no total and no gate. An inspected run shows what it
left out. The basis is shown in the backend's words.

**Tests.** Backend: thirteen tests no longer held. Twelve used an ordinary small item of
10,000 or less, below the CTT of 12,500, and now use amounts that accumulate; the
thirteenth, the boundary test, now pins 12,499.99 as not accumulated and 12,500.00 as
accumulated. Twelve tests were added: five on `core/gates.py`, six on the evaluation API
and one on the conclusion. Frontend: the captured
answers were regenerated from the API; four scenario amounts whose purpose was to move the
figures were raised above CTT (5,000 to 15,000 twice, 8,000 to 18,000 twice); the screen
tests read the new figures and two were added.

## D54 · A percentage below a line never reads 100% — 5 Nov 2026 (S6)

`percentOf()` in `frontend/src/format.ts` rounds half up to one decimal place, so a figure
from 99.95% of a line read "100.0%" although the line was not reached. The screen then
disagreed with the backend, which decides whether a line is reached. Now a figure strictly
below the line shows the largest percentage below 100 at that precision ("99.9%"); at or
above the line nothing changed. The arithmetic stays exact, with integers; the precision
and the rounding are unchanged and remain the CA's (S6). Presentation only (D16): nothing
is stored or sent, and no gate reads a percentage.

## D55 · Pass 1 closure: what a gate, a run and the conclusion form say — 5 Nov 2026

Small changes made while closing Pass 1. None changes a rule; each makes something the
module already knew visible where it was missing.

- **The gate endpoints name what their figures leave out.** `GET .../gates/opinion` and
  `.../gates/sign-off` (D18, D46) carry `not_accumulated`, the clearly trivial items of
  D53. A module that reads a gate was given figures and `complete: true` with nothing to
  say that some items were outside them.
- **An inspected run says whether it summed each item.** The column read "Counted: Yes"
  for every uncorrected item, a clearly trivial one included, beside the line that named
  it as not accumulated. It now reads from the run's own `counted` and `not_accumulated`
  lists ("No: clearly trivial"); a run that has neither list says only whether the item
  was uncorrected. Found in the browser, not by a test; a test now pins it.
- **The conclusion form shows the figures that will be saved** (spec section 6.4: "with
  the figures auto-inserted"): the four aggregates and the threshold version of the run
  reviewed, which the backend has just said still describes the evaluation. None is shown
  when there is no current run. Display only; no figure is sent.
- **The preview can show the strategy prompt.** `tests/preview_server.py` takes
  `--strategy-fraction`, a test value for that preview alone. It sets nothing for any real
  run: with no fraction declared the trigger is still not evaluated, and what the fraction
  should be is still B5.
- **One more question for the CA under S14** (question 9): a judgemental item is banded on
  its point estimate (D14, D33), so one whose estimate is below CTT is not accumulated even
  where its range reaches above PM. Built as it was; a test pins it and says it is not an
  answer. *(As at D55. Superseded by D56: such an item is now accumulated, and the test
  pins that.)*

## D56 · Two treatments taken from SA 450 paragraph A2 — 5 Nov 2026 (S14, questions 2 and 9)

*Item 2 below was superseded the same day by D57: showing the total and a note was not
enough. Item 1 stands.*

**Source.** ISA 450 as published by the FRC (ISA (UK) 450, https://www.frc.org.uk/docs/4512/html), read on 5 Nov 2026, and ICAI's exposure draft of SA 450, which carries the same requirements. ICAI's final SA 450 text was not read; the CA should confirm the wording against it. Paragraph 5: the auditor accumulates misstatements "other than those
that are clearly trivial". Paragraph A2: "When there is any uncertainty about whether one
or more items are clearly trivial, the matter is considered not to be clearly trivial", and
clearly trivial matters are described as inconsequential individually or in aggregate.
Neither treatment below is a decision of the CA; each is the conservative reading of that
paragraph, and each moves the module toward accumulating more, never less.

1. **A judgemental item whose range reaches CTT is not clearly trivial** (question 9).
   `core/banding.py`, `band_item()`: where both effects of a judgemental item band clearly
   trivial on the point estimate but either end of the auditor's range, in absolute terms,
   is at or above CTT, the item's band is accumulated and its basis says why. The amount
   accumulated is the point estimate, as for every judgemental item (D14). A range wholly
   below CTT leaves the item clearly trivial. Classification-only items are untouched. This
   amends D33 for that one case; nothing is stored, so it applies on the next read.
2. **What the clearly trivial items come to together is shown, and it is said when together
   they reach CTT** (question 2). `core/gates.py` totals the items left out, gross, on each
   measure; the evaluation and each run carry `not_accumulated_total` with the two totals,
   CTT and `at_or_above_ctt`. The screens show the totals and, when the flag is set, a note
   that the items together reach the threshold. *(As at D56; superseded by D57, under
   which such items are accumulated.)* **It changes no figure, no gate and no
   block**, and it is not in `figures()`, so nothing recorded is made stale by it. Whether
   such items should then be accumulated is still the CA's: the module now puts the fact in
   front of the auditor instead of leaving it invisible.

The other accounting readings (F3, B8, B14, B15a, B2) were checked against the same text
and stand as built; the register records the paragraph each rests on.

## D57 · Clearly trivial items that together reach CTT are accumulated — 5 Nov 2026 (S14, question 2)

**Source.** SA 450 as reproduced by ICAI's Board of Studies ("SA 450, Evaluations of Misstatements Identified during an Audit", © The Institute of Chartered Accountants of India, 15 June 2021, live.icai.org), read on 5 Nov 2026. The official copy at kb.icai.org could not be opened: its server presents a certificate for another ICAI address, and certificate checks were not switched off. The paragraphs quoted here are numbered as in the standard and agree word for word with ISA 450; the CA should still compare them with the official copy.

**Paragraph A2.** "The auditor may designate an amount below which misstatements would be clearly trivial and would not need to be accumulated because the auditor expects that the accumulation of such amounts clearly would not have a material effect on the financial statements. … Matters that are 'clearly trivial' will be of a wholly different (smaller) order of magnitude than materiality determined in accordance with SA 320, and will be matters that are clearly inconsequential, whether taken individually or in aggregate and whether judged by any criteria of size, nature or circumstances. When there is any uncertainty about whether one or more items are clearly trivial, the matter is considered not to be clearly trivial."

**What it settles.** The question was whether items that are each below CTT must be
accumulated when together they are not small. A2 answers it. The threshold exists only
because the auditor expects that accumulating such amounts "clearly would not have a
material effect"; a clearly trivial matter is one that is clearly inconsequential "whether
taken individually or in aggregate"; and any uncertainty about "one or more items" means
they are not clearly trivial. Items below CTT one by one are therefore not clearly trivial
once, together, they are not clearly inconsequential. D56 showed their total and raised a
note but still left them out of every figure and gate, so thirty items of 12,000 reached
no gate. That did not reflect A2 and is corrected.

**The rule built.** `core/gates.py`, `aggregate(items, ctt)`: the uncorrected items that
band clearly trivial one by one (classification-only items aside) are totalled gross, on
profit before tax and on net assets. While the total is below CTT on both measures they
are left out and named, as under D53. Once it is at or above CTT on either measure, all of
them are accumulated: they enter `counted`, every figure and every gate, and are named in
`not_accumulated_total.accumulated_together`. Each keeps its own band, clearly trivial,
because the band is computed from the item's amount (spec section 4). With no thresholds
there is no CTT and nothing is tested together.

**Why CTT, gross, on either measure.** The standard gives no number for "in aggregate". The
amount the auditor designated as clearly trivial is the only measure of triviality the
engagement has, so a total at or above it cannot be called clearly trivial without the
uncertainty A2 resolves against triviality. Gross, because A2 speaks of the accumulation of
such amounts and section 4.1 of the spec forbids netting between misstatements. Either
measure, because section 4.1 evaluates profit and net assets separately. Each choice is the
one that accumulates sooner. **These three choices are a reading, not the standard's words,
and are for the CA to confirm** (register S14, question 2, now narrowed to this).

**Consequences.** The rule has a step: one more small item can bring the whole group in.
That follows from A2 speaking of "one or more items" together. The figures then change, so
an acknowledgement or a strategy answer given before goes stale and a run made before is
stale, as for any other change. Nothing recorded earlier is touched. No model, migration,
route or database rule changed.

**Tests.** Unit: below CTT together they stay out; exactly at CTT all come in; either
measure suffices; opposite signs do not cancel; projected items among them stay projected;
without a threshold nothing is tested together. API: one item of 12,000 is left out, two
are accumulated, twenty-one reach the soft gate and block sign-off.

## D58 · Requests at the same moment, checked in a scratch schema — 5 Nov 2026 (V3)

The engagement row lock (D43, D45) had been proven one request at a time. Two transactions
can only meet over committed rows, and this module's tables allow no delete, so the suite,
which rolls everything back, could not show it. `backend/tests/concurrency_check.py` creates
a scratch schema in `oak_misstatements_test`, builds the tables there from the models, runs
the real application against it with the Spine double, and drops the schema in a `finally`.
The `public` schema is not written and `oak_misstatements` is not connected to.

Eight requests released together raise eight misstatements, each with its own reference,
and record eight evaluation runs, each with its own number; none fails. It is a tool run by
hand, not part of the suite, because it creates and drops a schema. It runs as the owner
role and without the migrations' triggers, which the lock does not depend on.

## D59 · Pass 2: the qualitative checklist and escalation — 6 Nov 2026 (spec 5, 9; acceptance 8; F5)

Pass 2 begins here, on instruction. The backend came first; the screens followed the same
day (D60).

**The record.** Table `qualitative` (migration 0011, model `QualitativeFactor`): the spec's
`misstatement · factor · note · escalated_by · at`, plus two columns that let an append-only
table express "update" and "remove". `applies` is true when an entry records a factor and
false when it clears one; `entry_no` orders a misstatement's entries and is issued under the
engagement row lock. The factors that apply now are those whose latest entry records them.
Nothing is updated or deleted: the database triggers and the application guard refuse it,
as for every other record. The factor is held to the seven of spec section 5 by a CHECK;
the reason is never blank, for a recording and for a clearing.

**The checklist** (`core/qualitative.py`) is the specification's seven, in its order and
words: law, regulation or loan covenant; a change in earnings or a trend; a ratio, including
the eleven Schedule III ratios; fraud or suspected fraud; a related party; segment
information or management remuneration; a loss turned into a profit, or the reverse. Which
apply is a person's judgement. Nothing detects one (spec section 12).

**Escalation.** A misstatement is escalated while at least one factor applies.

- *Listed individually* (acceptance 8): the evaluation's `tests.individual.escalated` names
  each uncorrected escalated item with its factors and its band; `aggregate.escalated` and
  each run's `detail.escalated` carry the references; every misstatement answer carries
  `qualitative: {escalated, factors}`, so the schedule shows it.
- *Accumulated whatever its band.* `gates.accumulates()` never leaves an escalated item out
  as clearly trivial. This is F5's reading, now built, and it rests on SA 450 paragraph A2:
  a matter is clearly trivial only when clearly inconsequential "whether judged by any
  criteria of size, nature or circumstances". An escalated item is therefore outside the
  group that D57 totals.
- *The band is unchanged.* It is still computed from the amount (spec section 4: "never
  chosen"); escalation is a separate fact beside it.
- *Runs.* `escalated` is one of the labels a run records, so escalating or clearing makes
  the latest run stale; where it moves a figure, an acknowledgement goes stale too.

**Not built, because the specification does not say it.** An escalated item does not block
sign-off and asks for no acknowledgement: section 7 lists the gates and escalation is not
among them. Whether it should is recorded as an open question, not assumed.

**The API.** `GET /api/misstatements/{id}/qualitative` (the checklist, whether escalated,
the history); `POST /api/misstatements/{id}/qualitative` with `{factor, note}` (record, or
record again with a new reason); `POST /api/misstatements/{id}/qualitative/{factor}/clear`
with `{note}`. A write appends an entry and answers 201. Refused: a factor outside the
seven, a blank reason, an actor or a timestamp in the body (422); clearing a factor that is
not recorded, or recording one again with the same reason (409). Any authenticated identity
may write, as for the module's other writes; who should is B9b.

**Migration 0011.** Applied to `oak_misstatements_test` on 6 November 2026, on approval, by
the PostgreSQL suite (which applies every unapplied migration to the test database). It is
not applied to `oak_misstatements`, which has no tables and still waits for approval (O2).

## D60 · The screens of the qualitative checklist — 6 Nov 2026 (spec 5, 10.1, 10.2; acceptance 8)

**One read.** A misstatement read on its own (`GET /api/misstatements/{id}`, and the answer
to raising or moving one) now carries the whole checklist in `qualitative`: `escalated`,
`factors`, `escalation_basis`, the seven `checklist` rows and the `history`. A row of the
schedule carries `escalated` and `factors` alone. The checklist's own endpoint answers the
same words with `misstatement_id` and `ref` (`services/qualitative.py`: `detail_json`,
`checklist_json`). So the detail screen needs no second request and holds no copy of the
seven factors: their wording is the backend's.

**Misstatement detail** (`components/misstatement/QualitativeFactors.tsx`, after the computed
effects, as spec section 10.2 orders it). The seven factors in the backend's order and
words, each recorded or not; a recorded one shows its reason, who recorded it and when.
A person chooses Record, New reason or Clear on a factor and must give a reason: the
confirm button stays disabled while the reason is blank, and the backend refuses a blank one
whatever the screen does. The write's answer is the checklist as it now stands and replaces
the one shown, with no second read. The history lists every entry, oldest first. A refusal
is shown in the backend's words and the form is kept. A write goes out once however often
it is confirmed. The header shows an "Escalated" pill beside the band, which stays the
amount's. Nothing suggests a factor (spec section 12).

**Schedule** (`components/ScheduleTable.tsx`). An escalated row shows "Escalated" beside its
band with the number of factors recorded, whatever the band.

**Evaluation** (`components/evaluation/GatesPanel.tsx`, "Individual items"). The escalated
items the backend lists (`tests.individual.escalated`) are named, each with its band by
amount, and the backend's basis is shown. This is where acceptance 8's "listed individually"
is read. Sign-off is not blocked by it (Q2 is open).

**The checklist is offered in every state**, as the backend allows (Q3 is open).

**Fixtures and tests.** Fourteen new captured answers (`qualitative-*.json`), produced by
`test_the_qualitative_fixtures_are_the_apis_real_answers`: the detail before, while and
after escalation, the answer to each write, three refusals, and the schedule and evaluation
of the engagement while escalated. `frontend/tests/Qualitative.test.tsx` holds 23 tests.

**Verified, 6 November 2026.** Backend `pytest` on PostgreSQL (`oak_misstatements_test`,
rolled back): 486 passed, 0 skipped. In memory: 454 passed, 32 skipped. `ruff`, `mypy`
strict clean (96 files). Frontend `vitest` 342 passed (19 files); `tsc`, `eslint`,
`prettier --check` clean; the production build succeeds. In a real browser, on the isolated
preview (the real application over the test database in one transaction that was never
committed; Spine test double; development identity): a factor recorded through the form on
a clearly trivial item, the schedule's mark and the totals moving from one item to two, the
evaluation's list, and the factor cleared through the form. Two misstatements were seeded
through the preview's API first. Not done: a named partner, the live Financial Spine, a
screen-reader session.

## D61 · Pass 2: prior-period uncorrected misstatements carried forward — 6 Nov 2026 (SA 450 para 11(b); spec 4.1, 9, 10.3; acceptance 5; B6)

Built on instruction, as an interim reading. B6 is not decided, and nothing here decides it.

**What the specification says, and what it leaves out.** Section 4.1: prior-period
uncorrected misstatements are "carried forward, with the current-period effect and the
cumulative effect shown separately, so the partner can see it both ways rather than being
handed one method". Section 9 gives the evaluation row a `py_carried` column and nothing
else. It does not say where a carried item comes from, whether it has Dr/Cr lines, or how
its effect on the current period is arrived at. Those are B6.

**The record.** Table `prior_period` (migration 0012, model `PriorPeriodItem`): one row per
version of one item of one engagement, append-only by trigger and by the application guard.
`ref` is `PY-1`, `PY-2`...; recording is version 1; revising the figures and removing the
item from the carry-forward are each a new version (`carried` false on the removing one,
whose `basis` holds the reason and which keeps the item's figures).

**The four figures are a person's.** Each version states the item's current-period effect
and its cumulative effect, on profit before tax and on net assets, with a mandatory `basis`
saying how they were arrived at. The module computes none of them: how a prior period's
misstatement runs through the current period (whether it reversed, whether it still stands)
is an accounting judgement (B6). Amounts are signed as the schedule signs an effect.

**Why the figures are held here.** A misstatement of the current year has an adjustment in
the Financial Spine, and its amounts live there (spec section 9). A carried item has none,
so its figures are on its own version. This is a consequence of B6 being open, not an
answer to it; `tests/test_models.py` lists the six columns as the one addition to the
module's money columns and says why.

**Rolling forward.** An item may cite a misstatement of another engagement of this module
(`source_misstatement_id`). The backend reads that misstatement itself: it must be
uncorrected there (raised, communicated or refused) with known effects, and it can be
carried once. Its description and its two effects there are copied onto the item
(`prior_profit`, `prior_net_assets`), never taken from the request. Its effects *here* are
still entered. An engagement carries no period, so the module cannot tell that the other
engagement is the prior period's: the person names the period.
`GET .../prior-period/candidates?from_engagement_id=` lists what could be rolled forward.

**What is computed** (`core/prior_period.py`, pure): the totals of the carried items on each
basis, gross (no netting between items) and net (signed), as spec section 4.1 sums
everything; and each total added to the current year's aggregate, giving "with prior-period
items" on the current-period basis and on the cumulative basis. Three things are therefore
shown apart: the current year's own misstatements, the prior-period items, and the two
together, both ways. A carried item is not banded and none is left out as clearly trivial.

**No gate reads any of it.** The hard gate, the soft gate, the strategy trigger and the
sign-off decision test the current year's aggregate exactly as before; with no item carried
every answer is what it was. The specification's section 7 does not say on which basis a
gate would test prior-period items, and choosing one would be "handing one method". So the
evaluation reports, as information, which measures of each "with prior-period" view are at
or above PM and OM (`prior_period.reaches`), says `read_by_gates: false`, and the two gate
endpoints carry the same block beside their status. Whether a gate should read these
figures, and on which basis, is recorded as an open question for the CA and the firm. Until
it is answered, an aggregate that reaches overall materiality only with prior-period items
does not block an unmodified opinion in this module: it is shown, not enforced.

**Evaluation runs.** `evaluation.py_carried` (migration 0012; nullable JSONB) records what a
run, and a conclusion, saw: which version of which item (labels) and the aggregates above.
Never one item's figures: those stay in the item's own unchangeable version. A run written
before the migration has none. Recording, revising or removing an item makes the latest run
and the latest conclusion stale. The four `agg_` columns remain the current year's.

**The API.** `GET /api/engagements/{id}/prior-period` (the schedule of carried items, the
removed ones, every version, the totals); `POST .../prior-period` (record by hand, or roll
forward with `source_misstatement_id`); `POST .../prior-period/{ref}/revisions`;
`POST .../prior-period/{ref}/removal` with `{reason}`;
`GET .../prior-period/candidates`. `GET .../evaluation` carries `prior_period`. Refused: a
missing or blank basis, a figure with more than two decimals, an actor or timestamp in the
body (422); revising or removing an item no longer carried, the same figures again, a
misstatement already carried or corrected (409). Any authenticated identity may write (B9b).

**The screen** (`components/evaluation/PriorPeriodPanel.tsx`, after the aggregate). Each
carried item with its current-period effect and its cumulative effect side by side, as two
column groups over profit before tax and net assets; then the current year, the
prior-period totals and the two together on each basis, with the percentage of PM and OM
and a mark where the backend says a line is reached; a statement that the gates do not read
these figures; a form to record an item by hand and one to stop carrying an item, each with
its mandatory words. A run's inspection names the items it saw. Revising an item and
rolling one forward are in the API and not on the screen.

**Verified, 6 November 2026.** Backend `pytest` on PostgreSQL (`oak_misstatements_test`,
rolled back; the run applied migration 0012 to that database): 506 passed, 0 skipped. In
memory: 470 passed, 36 skipped. `ruff`, `mypy` strict clean (104 files). Frontend `vitest`
360 passed (20 files); `tsc`, `eslint`, `prettier --check` clean; the build succeeds; 147
captured API answers, 11 of them new (`prior-period-*.json`). In a real browser, on the isolated preview (the real application over the test database in one transaction that was never committed; Spine test double; development identity): a prior-period item recorded through the form, its two effects and the three sets of totals shown, the mark and the note where the two together reach PM while the soft gate stayed clear and sign-off open, a run recorded and inspected with its carried items, and the item removed through the form, which made the run stale. The engagement, its thresholds and two misstatements were seeded through the preview's API first. Not done: a named
partner (so no conclusion carrying `py_carried` was made end to end), the live Financial
Spine, a screen-reader session, any run on the main database.

## D62 · Pass 2: the TCWG extract — 6 Nov 2026 (SA 450 para 12; spec 2 row 12, 6 item 2; acceptance 9)

Built on instruction. Read-only: `GET /api/engagements/{id}/tcwg-extract`. No table and no
migration: the extract is computed on every read from the evaluation as it stands, exactly
as the schedule and the gates compute it, so the three cannot disagree. It is a view of what
would be communicated, not a record that a communication was made.

**What the specification says.** Section 6 item 2: "uncorrected misstatements, material ones
individually named, with the effect on the opinion, and the request to correct". Section 4:
an item above PM is "flagged individually, listed by name in the TCWG communication".
Section 5: an escalated item "is listed individually regardless of size". Acceptance 9: "The
TCWG extract names every individually material item".

**Where each uncorrected misstatement falls** (`core/tcwg.py`, pure). Uncorrected is raised,
communicated or refused, the aggregate's own reading (F3). Each falls in exactly one place:

- *named individually*: banded individually significant (above PM), or escalated on a
  qualitative factor. Each says why, in words, and whether its own effect is at or above
  overall materiality. It carries what an item of its type must say (the range of a
  judgemental item, the sample and basis of a projected one), management's reason when
  refused, the qualitative factors with their reasons, and its Dr/Cr lines from the Spine;
- *could not be assessed*: it could not be banded (no thresholds, or its effects cannot be
  determined). It is named too, and the extract is marked `incomplete` with the reasons. An
  item is never left off the individual list on a guess;
- *other uncorrected*: accumulated and not named. Summarised by type, the three kept apart
  as spec section 3.2 keeps them, and listed;
- *clearly trivial, not accumulated*: outside the communication (spec section 4: "below it,
  not accumulated"), named apart with what they come to, so the extract reconciles to the
  schedule. Items clearly trivial one by one that are accumulated together (D57) are in
  "other", not here.

Corrected and withdrawn items are not uncorrected and are listed only as such.

**"Individually material" (B14).** The module shows both individual tests and chooses
neither. Every item at or above overall materiality is above PM, so naming everything above
PM names every individually material item on either reading. The extract says "named
individually" and gives the reason; it does not itself declare an item material.

**Totals.** The named items and the others are each summed gross (no netting) and net; the
two together are the evaluation's own aggregate, which the extract carries as it is, with
its count. The tests check that they tie to the paisa on every measure.

**The effect on the opinion** is the opinion gate's reading (D18), not a new rule:
`blocked`, `not_blocked` or `undetermined`, with the gate's own reasons, the line, the
highest measure, and the partner's conclusion when one is recorded. The gate tests the
current year's aggregate; the extract carries the prior-period items (D61) and says the
gate does not read them.

**The request to correct** is one fixed sentence, the standard's requirement put plainly:
"We request that the uncorrected misstatements set out in this schedule be corrected."
It applies when something uncorrected is accumulated or could not be assessed; otherwise the
extract says there is nothing to request. The firm's own wording, and whom the
communication is addressed to, are the firm's and are not built.

**The screen** (`pages/TcwgExtractPage.tsx`; tab "TCWG extract"; address
`#/engagements/{id}/tcwg-extract`). Laid out as a document: what is communicated, the
effect on the opinion, the misstatements named individually, those that could not be
assessed, the others summarised and listed, the totals, the prior-period items, what is
outside the communication, and the request. An incomplete extract says so at the top with
the reasons. "Print or save as PDF" hands the page to the browser's print dialog; the
application's header, tabs and buttons carry `print:hidden`. The page sends nothing.

**Verified, 6 November 2026.** Backend `pytest` on PostgreSQL (`oak_misstatements_test`,
rolled back; no new migration): 522 passed, 0 skipped. In memory: 486 passed, 36 skipped.
`ruff`, `mypy` strict clean (107 files). Frontend `vitest` 379 passed (21 files); `tsc`,
`eslint`, `prettier --check` clean; the build succeeds; 153 captured API answers, 6 of them
new. In a real browser, on the isolated preview (the real application over the test database in one transaction that was never committed; Spine test double; development identity): the extract opened from its tab, with two items named individually (one above PM, one escalated below the clearly-trivial threshold), the others summarised and listed, the totals, the clearly trivial item outside the communication, an unmodified opinion blocked and the request; no sideways scroll at 375 and 1280 pixels; the print rule present in the stylesheet. The engagement and its five misstatements were seeded through the preview's API. Not done: a printed page or PDF was not produced or inspected; a named
partner; the live Financial Spine; a screen-reader session.

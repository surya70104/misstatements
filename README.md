# OAK Audit · Misstatements Rollup — SA 450

Every misstatement found anywhere in the audit, accumulated in one schedule, classified
against the thresholds, aggregated, and carried into the opinion.

- Specification: [docs/MISSTATEMENTS_ROLLUP.md](docs/MISSTATEMENTS_ROLLUP.md) — the only
  source of requirements. Nothing is built that the specification does not ask for.
- Agreed decisions: [docs/architecture.md](docs/architecture.md)
- Open accounting and business decisions, never resolved in code:
  [docs/DECISIONS_PENDING.md](docs/DECISIONS_PENDING.md)

This is a standalone project. It does not read from, write to, or depend on the Financial
Spine project at `D:\CAF` or the Working Paper Binder at `D:\WORKING PAPER BINDER`, their
databases or their credentials. Integration with the Spine, the Binder, WorkMind and
Sampling goes through HTTP APIs only, each configured by a URL that may be unset.

## Layout

| Folder | Contents |
|---|---|
| `backend/` | Python 3.11 · FastAPI · SQLAlchemy · Alembic |
| `backend/src/oak_misstatements/` | `config.py` (settings and the database guard), `db.py`, `identity.py`, `errors.py`, `main.py` (the app factory) |
| `backend/src/oak_misstatements/models/` | `engagement`, `misstatement`, `misstatement_version` (spec section 9; D8, D9, D21), `threshold` and `event` (Stage 2), `misstatement_line_class` (the per-line classification snapshot, labels only, D32) |
| `backend/src/oak_misstatements/core/` | Pure logic: `effects.py` (profit before tax above item IX, net assets as assets less liabilities, per caption, classification-only when both are nil, `null` for both when a line cannot be classified; D31), `spine_kind.py` (the one place the Spine's adjustment kind is chosen; refuses classification-only items pending B2) |
| `backend/src/oak_misstatements/services/` | `spine_client.py` (the Financial Spine over HTTP), `engagements.py` (the Spine link), `misstatements.py` (raise and read over the Spine's lines) |
| `backend/src/oak_misstatements/schemas/` | Request shapes; acceptance 1 is checked here before anything reaches the Spine |
| `backend/src/oak_misstatements/api/` | Routers: health, engagements, misstatements |
| `backend/alembic/` | Migrations. 0001: the append-only trigger function and the money domain. 0002: the three Stage 1 tables, the record tables append-only. 0003: threshold and event. 0004: the classification snapshot, append-only, no amounts. 0005: PM below OM as a CHECK. 0006: the engagement's audit columns frozen, the app role limited to the Spine link columns. 0007: the state machine's CHECKs and INSERT trigger on `misstatement_version`. 0008: the `evaluation` row, append-only, one per run. 0009: the conclusion columns on that row and the hard gate as a trigger. 0010: the event kind held to the five the module writes |
| `backend/tests/` | `fake_spine.py` (the Spine double) and `local_stubs.py` (the double over HTTP on 8013); unit, schema, client, API and migration-SQL tests; database tests that skip until a test database exists |
| `frontend/` | React 19 · TypeScript · Vite · Tailwind · vitest · ESLint · Prettier |
| `scripts/db/` | One-time database and role creation scripts, run by a person as superuser. Not run yet |
| `docs/` | Specification, architecture decisions, pending decisions |

## Ports and tools

| Item | Value |
|---|---|
| API | <http://localhost:8003> |
| Frontend | <http://localhost:3003> |
| Test doubles for other modules | from 8013 |
| Python | 3.11, virtual environment at `backend\.venv` |
| Node | 22, selected through fnm (`.node-version` in `frontend/`) |
| Database | PostgreSQL 16 on localhost, databases `oak_misstatements` and `oak_misstatements_test` (not created yet) |

## Build stages

Pass 1 (spec section 11): the misstatement record with Dr/Cr lines over the Spine · the three
thresholds with automatic banding and recompute · the state machine with mandatory refusal
reasons · aggregation gross and net, profit and net assets · the schedule screen · the hard
gate at overall materiality · the documented conclusion. Pass 2: qualitative factors and
escalation · prior-period carry-forward · the TCWG extract and the written representation
attachment · intake hooks · projected misstatements from Sampling · the generated binder paper.

| Stage | Contents | Status |
|---|---|---|
| 0 | Git, folder structure, spec copy, architecture decisions D1–D20, pending-decisions register, backend package with settings guards, identity, app factory and health check, Alembic with migration 0001 (trigger function and money domain, no tables), frontend shell, database create scripts (not run), foundation tests, lint and type checks | done; see "Stage 0 verification" below |
| 1 | Spine client and double; engagement with its Spine link; the misstatement record with Dr/Cr lines proposed to the Spine at raise time, effects computed from the Spine's lines on every read, references issued once per engagement, append-only versions; migration 0002 | done; see "Stage 1 verification". B1 and B2 isolated, not decided (D23): no withdrawal behaviour, classification-only items refused naming B2. B7 built on 4 Nov 2026 (D31): profit before tax above item IX, net assets as assets less liabilities from the Spine's tree sections, `null` for both when a line cannot be classified; three CA confirmations outstanding |
| 2 | Thresholds: versioned OM, PM, CTT with the declared fraction and basis; superseded once, never deleted; the recompute event on revision; the Spine PM cross-check; banding; migration 0003 | done; see "Stage 2 verification". B3 and B11 closed at code level on 4 Nov 2026 (D33): both effects banded separately, the higher band wins, the spec's literal boundaries, acceptance 2 demonstrable. B13 closed the same day (D34): PM strictly below OM at the request and by migration 0005. B4 complete at code level (D35): manual entry as the interim, the Spine PM recorded and cross-checked, nothing pushed to the Spine, every version readable by id; three firm decisions stay pending. Still open: authorisation not enforced and declared (B9) |
| 3 | State machine: raised → communicated → corrected / refused / withdrawn; mandatory reasons; corrected posts to the Spine | done on 5 Nov 2026 (D41); see "Stage 3 verification". Every move is a new append-only version; a correction is accepted in the Spine and posts; a refusal and a withdrawal refuse the Spine's adjustment with the reason, so neither posts. Interim and open: withdrawal in the Spine (B1), reason categories (B12), leaving `raised` early (F4), edits (F9) |
| 4 | Aggregation gross and net, profit and net assets; the evaluation row | aggregate and gates built ahead of schedule on 4 Nov 2026 (D38): `GET /api/engagements/{id}/evaluation`, the write-path check `require_sign_off_open`, the partner-only soft-gate acknowledgement (D39). Completed on 5 Nov 2026 (D43); see "Stage 4 verification": both materiality tests shown, the reassessment prompt, and the append-only `evaluation` row, one per run (migration 0008). The conclusion and the strategy trigger (B5) are Stage 5 |
| 5 | Gates: OM hard gate, PM soft gate, strategy trigger, individually-significant block; the conclusion | done on 5 Nov 2026 (D45); see "Stage 5 verification". The conclusion is a new append-only `evaluation` row carrying its figures and threshold version (migration 0009), partner-only, naming the run reviewed; a conclusion of not material is blocked by every gate in the write path and by a database trigger at overall materiality; the strategy trigger is built with no default band (B5). Readings to confirm: B14, B15 |
| 6 | The schedule, misstatement detail and evaluation screens | built, reviewed and its gaps closed on 5 Nov 2026 (D47 to D52); see "Stage 6 closure verification". Nine screens over 24 of the 26 routes, used on live rows in an isolated preview. **Pass 1 implementation complete (`docs/CLOSURE_REVIEW.md` section 13); production acceptance pending:** the conclusion and the partner's acknowledgement have not been made by a named partner (V12), and nothing has been seen against the live Spine. In parts: Part 1 done on 5 Nov 2026 (D47); see "Stage 6 part 1 verification": routing, the typed API client, formatting, the shared loading, empty and error states, the layout, the engagement list, and the schedule address. Part 2 done on 5 Nov 2026 (D48); see "Stage 6 part 2 verification": the schedule screen with its ten columns, its filters by band, type and state, and the running totals against CTT, PM and OM; and the misstatement detail address. Part 3 done on 5 Nov 2026 (D49); see "Stage 6 part 3 verification": the misstatement detail screen with its identification, Dr/Cr lines and classification, effects, state history, and the moves of the state machine with their mandatory reasons. Part 4 done on 5 Nov 2026 (D50); see "Stage 6 part 4 verification": the evaluation screen with the aggregate against the three lines, the gates, the run history, recording a run, the strategy prompt, and the conclusion shown with what blocks it. The two partner-only writes are shown and never sent |
| 7 | Pass 1 acceptance run: criteria 1, 2, 3, 4, 6, 7, 10, 11 | |
| 8–14 | Pass 2 | Started 6 Nov 2026, on instruction. Stage 8, qualitative factors and escalation (spec section 5; acceptance 8): backend and screens built and tested, on PostgreSQL and in a browser on the isolated preview (D59, D60); migration 0011 is applied to the test database only. Stage 9, prior-period carry-forward (SA 450 paragraph 11(b); acceptance 5): backend and evaluation screen built and tested the same way, as an interim reading with B6 still open (D61); migration 0012 is applied to the test database only. Stage 10, the TCWG extract (SA 450 paragraph 12; acceptance 9): a read-only endpoint and its own screen, built and tested the same way (D62); no migration. Stage 11, the written representation attachment (SA 450 paragraph 14): a read-only endpoint and its own screen, built and tested the same way (D63); no migration. The rest of Pass 2 is not started |

## Setup on Windows

Everything below runs from `D:\MISSTATEMENTS_ROLLUP` in PowerShell unless a step says
otherwise. Nothing is installed system-wide: Python packages go into `backend\.venv`, Node
packages into `frontend\node_modules`. Both folders are ignored by git.

### Backend

```powershell
py -3.11 -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -c backend\requirements-lock.txt -e "backend[dev]"
Copy-Item backend\.env.example backend\.env
```

Open `backend\.env` afterwards and replace every `CHANGE_ME`. Until the databases exist the
placeholders are fine because nothing connects. Then, from `D:\MISSTATEMENTS_ROLLUP\backend`:

| Task | Command |
|---|---|
| Run the tests (database tests skip until `OAK_TEST_DATABASE_URL` is set) | `.venv\Scripts\python.exe -m pytest` |
| Lint | `.venv\Scripts\python.exe -m ruff check .` |
| Format check | `.venv\Scripts\python.exe -m ruff format --check .` |
| Type check | `.venv\Scripts\python.exe -m mypy` |
| Show migration SQL without connecting | `.venv\Scripts\python.exe -m alembic upgrade head --sql` |
| Run the API on port 8003 | `.venv\Scripts\python.exe -m uvicorn oak_misstatements.main:create_app --factory --reload --port 8003` |

The health check is at <http://localhost:8003/api/health> and the interactive API page at
<http://localhost:8003/docs>.

### Frontend

Node 22 is required and is selected through fnm. `frontend\.node-version` pins it, and
`frontend\.npmrc` makes npm refuse any other version, so the system Node 18 cannot be used
by accident. Either activate fnm once per shell:

```powershell
fnm env --use-on-cd | Out-String | Invoke-Expression
```

or prefix each command with `fnm exec --using=22 --`. From `D:\MISSTATEMENTS_ROLLUP\frontend`:

| Task | Command |
|---|---|
| Install packages (once, and after `package.json` changes) | `npm install` |
| Run the tests | `npm test` |
| Type check | `npm run typecheck` |
| Lint | `npm run lint` |
| Format check | `npm run format` |
| Start the dev server on port 3003 | `npm run dev` |
| Production build into `frontend\dist` | `npm run build` |

The dev server proxies `/api` to the backend on 8003, so start the backend first and open
<http://127.0.0.1:3003>.

### Database: one-time creation, run by a person

The module uses two databases of its own on the PostgreSQL 16 server, `oak_misstatements`
and `oak_misstatements_test`, and two roles, `oak_misstatements_owner` (migrations) and
`oak_misstatements_app` (the API). They are created once by `scripts\db\02_create.sql`, run
as the `postgres` superuser. The script checks that none of the four names exist and stops
without changing anything if one does. It never drops anything and never refers to any other
project's databases or roles. **Neither script has been run yet** (pending decision O2).

First, the read-only pre-check:

```powershell
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -h localhost -p 5432 -U postgres -d postgres -f scripts\db\01_check_names.sql
```

Then the creation script:

```powershell
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -h localhost -p 5432 -U postgres -d postgres -f scripts\db\02_create.sql
```

Then, in psql, set the two passwords. psql hides what you type and sends only a hash.

```powershell
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -h localhost -p 5432 -U postgres -d postgres -c "\password oak_misstatements_owner" -c "\password oak_misstatements_app"
```

Put the passwords into `backend\.env`, replacing `CHANGE_ME`, and uncomment the two
`OAK_TEST_*` lines so the database tests run. Then apply the migration from `backend\`:

```powershell
.venv\Scripts\python.exe -m alembic upgrade head
```

### Who acts (B9, D36)

Every write needs an identity: `OAK_AUTH=dev` with `OAK_DEV_USER` in development, or
`OAK_AUTH=header` behind an authenticating proxy, believed only from `OAK_TRUSTED_PROXIES`.
A missing, blank, duplicated or implausible identity refuses the write. The identity is
recorded as `created_by`, `raised_by`, `set_by` or the event `actor`, taken from the
request's identity source and never from its body; a body that names an actor is refused.
Every audit column is frozen at the database. **No general role model is enforced**: any
authenticated identity may raise, link and set thresholds, which the spec leaves to anyone.
**Partner-only actions are enforced and fail closed** (D39, D45): the soft-gate acknowledgement
and the conclusion succeed only when `OAK_TRUSTED_PROXIES` lists the proxy, the proxy presents the signed-in
user's roles in `OAK_AUTH_ROLES_HEADER` and `OAK_PARTNER_ROLE` is among them as a whole
value; without any of that, in dev mode, from an unlisted peer, or with a missing,
duplicated or non-matching claim it answers 403 and writes nothing (D40). No role is read from a request body or inferred from a name. Every answer carries
an `authorisation` block with the identity mode, whether it is production grade, and
`partner_actions.available`. A development identity is never evidence of authorisation.

### What the settings refuse

Every database URL is checked at startup, before any connection (architecture D5): it must
use the `postgresql+psycopg` driver, give host and port, be on localhost, name
`oak_misstatements` or `oak_misstatements_test`, and connect as the role the URL is for
(`oak_misstatements_app` for the API, `oak_misstatements_owner` for migrations and the
test-owner URL). Production refuses `OAK_AUTH=dev`, `OAK_DEV_USER`, an empty
`OAK_TRUSTED_PROXIES`, a plain-http service URL off the loopback interface, and the test
database. `tests\test_config.py` proves each rule.

## The API so far

Interactive documentation is at <http://localhost:8003/docs> when the API runs. Every
amount in an answer is an exact decimal string; every effect is computed from the Spine's
lines at the moment of the request, never stored here.

| Method and path | What it does |
|---|---|
| `GET /api/health` | The API is up; touches no database |
| `POST /api/engagements`, `GET /api/engagements` | Create an engagement, optionally linked to a Spine engagement and version (verified against the Spine); list engagements |
| `GET /api/engagements/{id}` | The engagement with its Spine link status: unlinked, not configured, verified (with the version's lock state), missing, unreachable, mismatch |
| `POST /api/engagements/{id}/spine-link` | Set, change or clear the link. Changing the pinned version once a misstatement exists is refused naming pending decision B10 |
| `POST /api/engagements/{id}/misstatements` | Raise a misstatement: balanced Dr/Cr lines (acceptance 1), type with its own fields (spec 3.2), a working paper reference (spec section 8). Proposed to the Spine with our reference in `finding_ref`: as a `correction`, or as a `reclass` when both effects are nil (classification only, D37); refused when a ledger has no head, the version is locked or unpinned, or no Spine is configured |
| `GET /api/engagements/{id}/misstatements` | Every misstatement's current version with the Spine's lines, the computed effects, and the Spine's own status for the adjustment |
| `GET /api/misstatements/{id}` | One misstatement with every version. Every answer carries `band` (clearly_trivial, accumulated, individually_significant, or `null` with the reason) and a `banding` block: both effects' bands and amounts, the threshold version used, `projected`, and `range_crosses_pm` for a judgemental item (D33) |
| `POST /api/misstatements/{id}/transitions` | Move a misstatement: `communicated`, then `corrected`, `refused` (reason mandatory, acceptance 3) or `withdrawn` (reason mandatory). A new append-only version each time. `corrected` accepts the Spine's adjustment, which posts (acceptance 11); `refused` and `withdrawn` refuse it with the reason, which posts nothing. Any other move is a 409 naming the allowed ones (D41) |
| `POST /api/engagements/{id}/thresholds` | Set a threshold version: OM, PM, the declared CTT fraction (no default) and the basis. Supersedes the current version once and records a `threshold_recompute` event with the changes. Answers with the Spine PM cross-check, the PM-below-OM check (reported, not enforced) and the authorisation notice (not enforced, pending B9) |
| `GET /api/engagements/{id}/thresholds` | The current version with the Spine PM cross-check: match, mismatch, spine_has_no_pm, not_pinned, not_configured, unreachable |
| `GET /api/engagements/{id}/thresholds/history` | Every version, newest first, with `superseded_by` |
| `GET /api/thresholds/{id}` | One version by id, current or superseded, with the Spine PM cross-check against the version it was set against (D35) |
| `GET /api/engagements/{id}/events` | The engagement's event trail: `threshold_recompute` and `soft_gate_acknowledged` |
| `GET /api/engagements/{id}/evaluation` | The aggregate (gross and net, profit and net assets, with and without projected items), the hard and soft gates with the measures that reached the line and whether they depend on projected items, the individually significant items that block, the acknowledgement status, and the sign-off decision with its reasons (D38) |
| `POST /api/engagements/{id}/evaluation/runs` | Record an evaluation run: one append-only row with the current threshold version and the four aggregates, plus labels of every misstatement seen. `materiality_reassessed: true` is required (SA 450 paragraph 10). Refused with 409 when thresholds are missing, an effect is unresolved or a state disagrees with the Spine. A gate that fires does not stop a run (D43) |
| `GET /api/engagements/{id}/evaluation/runs`, `GET /api/evaluation-runs/{id}` | Every run of an engagement, newest first; one run by id, exactly as recorded |
| `POST /api/engagements/{id}/evaluation/conclusions/not-material` | Partner only. Conclude that the uncorrected misstatements are not material: a new append-only row with the figures, the threshold version, the conclusion and its basis together. Needs `conclusion`, `basis`, `reviewed_run_id` and `materiality_reassessed: true`. Blocked (409) by the hard gate, by the soft gate without a current acknowledgement or with `OAK_PM_GATE=hard`, by an item above PM not yet dealt with, by anything unresolved, and when the run reviewed is stale (D45) |
| `POST /api/engagements/{id}/evaluation/conclusions/material` | Partner only. Conclude that they are material. Same body. A gate that fires does not block it; an unknown or unfinished evaluation and a stale reviewed run do (D45) |
| `GET /api/engagements/{id}/evaluation/conclusions` | Every conclusion, newest first, each with its figures and threshold version |
| `POST /api/engagements/{id}/evaluation/strategy-responses` | Record the answer to the strategy prompt, whether the strategy and plan were revised. Any authenticated identity. Refused unless the trigger fires, which needs `OAK_STRATEGY_TRIGGER_FRACTION` (no default, B5) |
| `GET /api/engagements/{id}/gates/opinion` | Read-only, for the module that issues the opinion (D18): `open`, `blocked` or `undetermined`, with the figures, the threshold version and why. Blocked when the aggregate is at or above overall materiality, or at or above performance materiality where the firm set that gate to hard |
| `GET /api/engagements/{id}/gates/sign-off` | Read-only (D18): the whole sign-off decision as `open`, `blocked` or `undetermined`, with the figures and every reason |
| `GET /api/engagements/{id}/spine-reconciliation` | Read-only (D46): orphan Spine proposals, records whose adjustment the Spine lacks, states the two modules disagree on. Repairs nothing |
| `POST /api/engagements/{id}/evaluation/soft-gate-acknowledgements` | Partner only: record the acknowledgement of the soft gate on the current figures as an append-only event. Fails closed without a trusted role claim (D39) |

This table is as it stood at Pass 1. The Pass 2 endpoints (the qualitative checklist, the
prior-period carry-forward and the TCWG extract) are listed in their own sections below.
Not yet, by design: no edit (F9), no Opinion hand-off. Every misstatement answer carries `state_consistency`, which
says whether the state here and the Spine's adjustment agree.

## B7 verification (net assets effect)

Run on 4 November 2026 after D31:

- Backend: `ruff check` and `ruff format --check` clean, `mypy` strict clean (55 files),
  `pytest` 161 passed, 14 skipped (the same 14 database tests, pending O2).
- `tests\test_effects.py` runs the eighteen-row matrix on sections directly and a
  hypothesis sweep proving net assets equals the mirror of profit-and-loss and equity lines
  for any balanced entry; `tests\test_api_misstatements.py` runs the matrix through the
  Spine double, including the two regressions (a tax line no longer moves profit before
  tax; a direct equity entry is no longer "classification only"), share application money
  refused as unresolved, and an entry whose head disappears from the tree showing `null`
  effects on read rather than a partial total.
- Not run: the real Financial Spine; its tree was read from CAF's source, not fetched live.

## Stage 3 verification

Run on 5 November 2026:

- Backend: `ruff check` and `ruff format --check` clean, `mypy` strict clean (74 files),
  `pytest` 312 passed, 21 skipped (every database test, pending O2).
- `tests\test_states.py` checks all twenty-five state pairs against the diagram, what each
  final state asks of the Spine, and that the longest note fits the Spine's limit.
  `tests\test_api_transitions.py` proves, on the stand-in and the Spine double: each valid
  move with its date; acceptance 11 both ways (a correction moves the adjusted balance by
  exactly its lines, and a raised, communicated, refused or withdrawn item never does);
  acceptance 3 and the withdrawal reason; every invalid move refused with nothing written;
  unknown fields, actors and dates in the body refused; the trail (earlier versions
  byte-identical, a snapshot per version, `raised_by` constant, `created_by` per move);
  identity required in both modes; a Spine failing exactly at the decision, unreachable,
  unconfigured, locked or missing the adjustment; a database failure stopping the move
  before the Spine is asked; a decision taken in the Spine directly being reported,
  blocking sign-off and being completable; and the gates following the state.
- `tests\test_migration_sql.py` proves migration 0007 from its rendered SQL; three
  `db`-marked tests will prove the CHECKs and the trigger on PostgreSQL once a test
  database exists. `tests\test_spine_client.py` proves the decision call.
- Frontend unchanged: `eslint`, `tsc --noEmit`, `prettier --check` clean, `vitest` 5 passed.
- Not run: PostgreSQL (the trigger's PL/pgSQL has never executed) and the live Financial
  Spine (its decision endpoint was read from CAF's source and mirrored in the double).

## Pass 2, feature 1: qualitative factors and escalation (D59)

Built on 6 November 2026: backend (D59) and screens (D60).

- **The checklist** of spec section 5, seven factors, recorded against a misstatement with a
  mandatory reason. `GET /api/misstatements/{id}/qualitative` reads it;
  `POST /api/misstatements/{id}/qualitative` records a factor or records it again with a
  new reason; `POST /api/misstatements/{id}/qualitative/{factor}/clear` clears one. Entries
  are appended and never changed (table `qualitative`, migration 0011).
- **Escalation.** A misstatement with at least one factor recorded is escalated: listed
  individually in the evaluation whatever its size (acceptance 8), flagged in the schedule,
  and accumulated even when it is below the clearly-trivial threshold. It does not block
  sign-off; whether it should is an open question (`docs/DECISIONS_PENDING.md`, last
  section).
- **Screens.** The misstatement detail shows the checklist: record a factor, give it a new
  reason or clear it, each with a mandatory reason, and the full history. The schedule marks
  an escalated row "Escalated" beside its band. The evaluation lists the escalated items
  under "Individual items".
- **Migration 0011** was applied to `oak_misstatements_test` on approval. The main database
  is untouched.
- **Tests, 6 November 2026, after this feature:** backend `pytest` on PostgreSQL **486 passed, 0
  skipped**; on the in-memory stand-in **454 passed, 32 skipped**; `ruff` and `mypy` strict
  clean (96 files); frontend `vitest` **342 passed** (19 files); `tsc`, `eslint`, `prettier`
  clean; build succeeds; 136 captured API answers. Checked in a browser on the isolated
  preview (test database, never committed; Spine test double). The latest counts are in
  the next section.

## Pass 2, feature 2: prior-period carry-forward (D61)

Built on 6 November 2026, as an interim reading. Pending decision B6 is still open.

- **The record.** A prior-period uncorrected misstatement is recorded against an engagement
  with four figures, each entered by a person with a mandatory basis: its current-period
  effect and its cumulative effect, on profit before tax and on net assets. The module
  computes none of them. Table `prior_period` (migration 0012), append-only: revising and
  removing an item are new versions.
- **Rolling forward.** An item may cite a misstatement of another engagement, uncorrected
  there; the backend copies its description and its effects there. Its effects here are
  still entered.
- **The evaluation** shows three things apart: the current year's own aggregate, the
  prior-period totals on each basis, and the two together on each basis, gross and net.
- **No gate reads the prior-period figures.** The gates and sign-off test the current year's
  aggregate as before. The evaluation says which lines the two together reach, as
  information. Whether a gate should read them, and on which basis, is an open question
  (`docs/DECISIONS_PENDING.md`, last section, P1).
- **Runs.** `evaluation.py_carried` records which version of which item a run saw, and the
  aggregates. A change to a carried item makes the latest run and conclusion stale.
- **API.** `GET` and `POST /api/engagements/{id}/prior-period`;
  `POST .../prior-period/{ref}/revisions`; `POST .../prior-period/{ref}/removal`;
  `GET .../prior-period/candidates?from_engagement_id=`.
- **Screen.** The evaluation screen has a "Prior-period uncorrected misstatements" panel:
  each item with its two effects side by side, the three sets of totals, and forms to record
  an item and to stop carrying one. Revising and rolling forward are API only.
- **Tests, 6 November 2026, after this feature:** backend `pytest` on PostgreSQL **506 passed, 0
  skipped**; on the in-memory stand-in **470 passed, 36 skipped**; `ruff` and `mypy` strict
  clean (104 files); frontend `vitest` **360 passed** (20 files); `tsc`, `eslint`,
  `prettier` clean; build succeeds; 147 captured API answers. The latest counts are in the
  next section.

## Pass 2, feature 3: the TCWG extract (D62)

Built on 6 November 2026. Read-only; nothing is stored and there is no migration.

- **`GET /api/engagements/{id}/tcwg-extract`** returns the uncorrected misstatements for
  communication to those charged with governance (SA 450 paragraph 12).
- **Named individually** (acceptance 9): every uncorrected item above performance
  materiality and every item escalated on a qualitative factor, each with the reason, its
  effects, its Dr/Cr lines and what its type must say. An item that could not be banded is
  named as not assessed and the extract is marked incomplete.
- **The others** are summarised by type and listed. Clearly trivial items that are not
  accumulated are outside the communication and are named apart.
- **Totals** of the named items and of the others, gross and net; together they are the
  evaluation's own aggregate.
- **Effect on the opinion:** the opinion gate's reading (blocked, not blocked or
  undetermined) with its reasons. Prior-period items are shown and are not part of that test.
- **The request to correct:** one fixed sentence from the standard's requirement. The
  firm's wording is not built.
- **Screen:** the "TCWG extract" tab of an engagement, laid out as a document, with "Print
  or save as PDF" through the browser's print dialog.
- **Tests, 6 November 2026, after this feature:** backend `pytest` on PostgreSQL **522 passed, 0
  skipped**; on the in-memory stand-in **486 passed, 36 skipped**; `ruff` and `mypy` strict
  clean (107 files); frontend `vitest` **379 passed** (21 files); `tsc`, `eslint`,
  `prettier` clean; build succeeds; 153 captured API answers. The latest counts are in the
  next section.

## Pass 2, feature 4: the written representation attachment (D63)

Built on 6 November 2026. Read-only; nothing is stored and there is no migration.

- **`GET /api/engagements/{id}/rep-letter-attachment`** returns the summary of uncorrected
  misstatements in the form that attaches to the representation letter (SA 450 paragraph 14).
- **The summary:** every accumulated uncorrected misstatement, by type (factual,
  judgemental, projected), each type and the whole summed gross and net, on profit before
  tax and separately on net assets. The whole is the evaluation's own aggregate.
- **Prior-period items** carried forward are included with both effects, apart from the
  totals.
- **The statement:** one fixed sentence from the standard's requirement, that management
  and those charged with governance believe the effects are immaterial, individually and in
  aggregate. It is management's belief, not the auditor's conclusion, and it changes nothing
  in the evaluation. The firm's wording is not built.
- **Cautions, for the auditor:** where the evaluation does not sit with the statement (an
  item not yet communicated, an item above PM, an opinion blocked, a conclusion of
  material, no current run), the answer says so. None blocks the attachment.
- **Screen:** the "Representation attachment" tab of an engagement, with "Print or save as
  PDF". The printed page is the attachment alone; the cautions are on screen only.
- **Tests, 6 November 2026 (latest):** backend `pytest` on PostgreSQL **540 passed, 0
  skipped**; on the in-memory stand-in **504 passed, 36 skipped**; `ruff` and `mypy` strict
  clean (110 files); frontend `vitest` **395 passed** (22 files); `tsc`, `eslint`,
  `prettier` clean; build succeeds; 159 captured API answers. These supersede the counts in
  every other section, which are those of their own dates.

## Clearly trivial items and the percentage display (D53, D54)

Built on 5 November 2026, after the Stage 6 closure work below.

**The test results in this section are the latest known (5 November 2026).** Every other
count in this file is the count on the date of its own section and is kept as a record.

- **A clearly trivial misstatement is not accumulated** (spec sections 2 and 4; D53). The
  aggregate, and so every gate, run, acknowledgement and conclusion, leaves out an
  uncorrected item below the clearly-trivial threshold and names it in
  `aggregate.not_accumulated`. It stays in the schedule. Since D57 this holds only while
  such items together stay below the threshold (see below). Of the nine questions the spec
  does not answer, one is still with the CA (`docs/DECISIONS_PENDING.md`, S14 question 2).
- **A percentage below a line never reads 100%** (D54): 99.9% is shown instead.
- Backend: `pytest` on PostgreSQL **469 passed, none skipped**; on the stand-in 437 passed,
  32 skipped. `ruff check`, `ruff format --check` and `mypy` strict are clean (89 files).
- Frontend: `vitest` **319 passed in 18 files**; `tsc --noEmit`, `eslint src tests` and
  `prettier --check .` are clean; `npm run build` succeeds.
- The Pass 1 workflow was walked twice in a browser on the isolated preview, through the
  forms and buttons (D55), and the D57 display was checked in a third session. Not seen
  with a named partner or against the live Financial Spine.
- **From SA 450 paragraph A2 (D56, D57):** a judgemental item whose range reaches the
  clearly-trivial threshold is accumulated; and items that are clearly trivial one by one
  are left out only while together, gross, they are below that threshold. Once together
  they reach it, all of them are accumulated and the gates see them. The measure of "in
  aggregate" is a reading for the CA to confirm.
- `docs/DECISIONS_PENDING.md` ends with the resolution pass and a final targeted review:
  49 items were open, 31 are closed and **18 remain**, each with who or what it waits on
  and why it cannot be closed inside this project.
- Requests at the same moment were checked with `backend\tests\concurrency_check.py`, in a
  scratch schema of the test database that is dropped afterwards (D58).
- `docs/CLOSURE_REVIEW.md` section 13 is the Pass 1 closure: the seven deliverables, the
  acceptance criteria, what was fixed, and every decision and dependency still open. Its
  verdict: the implementation is complete; production acceptance waits on a named
  partner, the live Spine and the CA.

The figures in the next section, and in every section after it, are those of their own
dates, before this change.

## Stage 6 closure verification (D52)

Run on 5 November 2026, after the closure work on S1 to S12 and V9 to V11. The matrix is
`docs/CLOSURE_REVIEW.md` section 11.

- Frontend: `vitest` **310 passed in 18 files**, three runs in a row. `tsc --noEmit`,
  `eslint src tests` and `prettier --check .` are clean. `npm run build` succeeds. No
  dependency was added.
- Backend: `pytest` on PostgreSQL **450 passed, none skipped**; on the stand-in 418
  passed, 32 skipped. `ruff check`, `ruff format --check` and `mypy` strict are clean (88
  files). The backend's source and migrations are unchanged since the last commit; the two
  backend files touched are test tooling, `tests\test_frontend_fixtures.py` and
  `tests\preview_server.py`.
- Fixture tests: 122 captured answers of the real API, checked on both backends. They cover
  the five new screens, the partner's two forms (captured with the app behind a trusted
  proxy with a role claim) and the eight display branches that had none.
- **Live, in an isolated preview that kept nothing:** an engagement, thresholds and their
  revision, six misstatements, every move of the state machine, an evaluation run, the soft
  gate and the hard gate, the event trail and the reconciliation were all done from the
  screens against a running backend on PostgreSQL. The three partner-only writes were
  refused with a 403. Afterwards the test database held no row.
- **Not verified:** a partner's acknowledgement or conclusion through a browser, which
  needs the firm's identity provider; the strategy prompt on a running backend, which needs
  a value for `OAK_STRATEGY_TRIGGER_FRACTION` (B5); anything against the live Financial
  Spine. No migration has been applied to `oak_misstatements`. Nothing is committed.

### Looking at the screens on live rows without keeping anything

```
cd backend
.venv\Scripts\python.exe -m tests.preview_server --port 8014
```

Build the frontend first (`npm run build` in `frontend`), then open
<http://127.0.0.1:8014>. Everything done there is inside one transaction on
`oak_misstatements_test` that is rolled back when the process ends. The Financial Spine is
the test double; to pin an engagement use the double's engagement
`11111111-1111-4111-8111-111111111111` and version
`aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1`. Do not run the test suite on PostgreSQL while the
preview is open.

## Stage 6 final verification (D51)

Run on 5 November 2026, after the four parts. The full review is `docs/CLOSURE_REVIEW.md`
section 10.

- Frontend: `vitest` **221 passed in 14 files**. `tsc --noEmit`, `eslint src tests` and
  `prettier --check .` are clean. `npm run build` succeeds. No dependency was added in
  Stage 6.
- Backend: `pytest` on PostgreSQL **447 passed, none skipped**; on the stand-in 415
  passed, 32 skipped. `ruff check`, `ruff format --check` and `mypy` strict are clean (87
  files). The backend's source and migrations are unchanged since the last commit; the one
  file Stage 6 added is `backend\tests\test_frontend_fixtures.py`.
- New in this review: one test walks engagement list, schedule, detail, evaluation and back
  by the links on the screens; one follows every link on every screen and finds no dead
  one; three read every rupee amount off the screens and require each to be a figure the
  backend sent, digit for digit.
- In a browser, with the API's captured answers standing in for it: no screen scrolls
  sideways at 1280, 768 or 375 pixels; no error or warning is logged on a pass through
  every screen; no write was sent to the running backend.
- One defect found and fixed: a dash too pale to read on the misstatement detail.
- **What Stage 6 does not do** (register S1 to S3): no screen sets or documents
  thresholds, none creates an engagement or raises a misstatement, and the conclusion and
  the soft-gate acknowledgement are shown and cannot be recorded from a screen.
- **Not done:** no migration has been applied to `oak_misstatements`; no record was written
  to either database; nothing was committed; no screen has been seen on live data (V9), and
  no write has been sent from a screen to a live backend (V10).

## Stage 6 part 4 verification (D50)

Run on 5 November 2026:

- Frontend: `vitest` **212 passed in 13 files** (146 before; every earlier test is kept).
  `tsc --noEmit`, `eslint src tests` and `prettier --check .` are clean. No dependency was
  added.
- The evaluation screen is tested against the API's own answers for fifteen moments of
  six engagements: every gate clear, firing, and indeterminate; with and without projected
  items; an incomplete aggregate; no run, a current run, a stale run and two runs; the
  strategy prompt before and after its answer; and a conclusion recorded, stale and
  replaced. The conclusion fixtures were captured with the app in header mode behind a
  trusted proxy, with a partner's role claim. The two tests that a write goes out only once
  were checked by removing the guard: they then fail.
- Backend, unchanged apart from the fixture test module: `pytest` on PostgreSQL **447
  passed, none skipped**; on the stand-in 415 passed, 32 skipped. `ruff check`,
  `ruff format --check` and `mypy` strict are clean (87 files).
- In the browser the screen was looked at with the captured fixtures standing in for the
  API's answers, at 1280 and 375 pixels: with no gate firing, with the hard gate firing,
  with two conclusions, recording a run, and inspecting a run. One defect was found and
  fixed there: at 375 pixels an inspected run made the page scroll sideways. The run was
  answered by the fixture inside the page: **no write was sent to the running backend.**
- **Not done:** no migration has been applied to `oak_misstatements`. No record was written
  to either database. Neither write has been sent from the screen to a live backend. The
  two partner-only writes cannot be exercised in development mode by design.

## Stage 6 part 3 verification (D49)

Run on 5 November 2026:

- Frontend: `vitest` **146 passed in 11 files** (97 before; the four tests of the
  header-only detail page were replaced by the tests of the detail itself, and one app
  test's assertion about that page was updated). `tsc --noEmit`, `eslint src tests` and
  `prettier --check .` are clean. No dependency was added.
- Every state and every move is tested against the API's own answers: the same misstatement
  read as raised, communicated and corrected; a judgemental one refused; a projected one
  withdrawn; a classification-only one, before and after the Spine reclassified a ledger;
  one read with the Spine unreachable; and the backend's refusals. The test that a move
  goes out only once was checked by removing the guard: it then fails.
- Backend, unchanged apart from the fixture test module: `pytest` on PostgreSQL **445
  passed, none skipped**; on the stand-in 413 passed, 32 skipped. `ruff check`,
  `ruff format --check` and `mypy` strict are clean (87 files).
- In the browser the detail page, a move from raised to communicated with its processing
  state, a refused misstatement and one read with the Spine unreachable were looked at with
  the captured fixtures standing in for the API's answers, at 1280 and 375 pixels. The move
  was answered by the fixture inside the page: **no write was sent to the running backend.**
- **Not done:** no migration has been applied to `oak_misstatements`. No record was written
  to either database. A move has not been sent from the screen to a live backend.

## Stage 6 part 2 verification (D48)

Run on 5 November 2026:

- Frontend: `vitest` **97 passed in 9 files** (58 before; the seven tests of the header-only
  schedule page were replaced by the tests of the schedule itself). `tsc --noEmit`,
  `eslint src tests` and `prettier --check .` are clean. No dependency was added.
- The schedule is tested against the API's own answers: one engagement carrying every type,
  state and band, one with nothing raised, and the first again with the Spine unreachable.
  `backend\tests\test_frontend_fixtures.py` produces and checks them; it passes on
  PostgreSQL and on the stand-in and leaves the test database empty.
- Backend, unchanged apart from that one test module: `pytest` on PostgreSQL **444 passed,
  none skipped**; on the stand-in 412 passed, 32 skipped. `ruff check`,
  `ruff format --check` and `mypy` strict are clean (87 files).
- In the browser the schedule, the pinned totals, the three filters, the detail address and
  the way back were looked at with the captured fixtures standing in for the API's answers,
  at 1440, 1280, 1024 and 375 pixels: the page never scrolls sideways. That is a check of
  appearance and behaviour, not of live data: the running backend's database holds no
  engagement, and none was created.
- **Not done:** no migration has been applied to `oak_misstatements`. No record was written
  to either database.

## Stage 6 part 1 verification (D47)

Run on 5 November 2026:

- Frontend: `vitest` **58 passed in 7 files** (routing, API errors, formatting, the shared
  states, the engagement list, the schedule header, the shell; the five earlier tests are
  among them and unchanged in meaning). `tsc --noEmit`, `eslint src tests` and
  `prettier --check .` are clean. No dependency was added.
- The fixtures the screens are tested against are the API's own answers, produced and
  checked by `backend\tests\test_frontend_fixtures.py`. It passes on PostgreSQL and on the
  stand-in and leaves the test database empty.
- Backend, unchanged apart from that one test module: `pytest` on PostgreSQL **443 passed,
  none skipped**; on the stand-in 411 passed, 32 skipped. `ruff check`,
  `ruff format --check` and `mypy` strict are clean (87 files).
- In the browser, against a running backend: the engagement list loaded with
  `GET /api/engagements` answering 200 and showed its empty state, because that backend's
  database held no engagement; an unknown engagement address showed the backend's own 404
  message with a retry. The filled list and the schedule header were looked at in the
  browser with the captured test fixture standing in for the two answers, at desktop width
  and at 375 pixels. That is a check of appearance, not of live data.
- **Not done:** no migration has been applied to `oak_misstatements`, so a backend pointed
  at it cannot answer the list. No engagement was created anywhere for the purpose of the
  check. The page has no favicon, so the browser logs one 404 for `/favicon.ico`.

## PostgreSQL verification on the test database

Run on 5 November 2026, PostgreSQL 16.15:

- A person created the two roles and two databases with `scripts\db\02_create.sql` and set
  the passwords. `backend\.env` holds the four URLs and is ignored by git.
- Migrations 0001 to 0010 were applied to `oak_misstatements_test` as the owner role, driven
  from code with the test URL only. All ten applied cleanly. The schema matches the models:
  every table, column and named constraint, twenty triggers, seven functions, the money
  domain, and the application role holding SELECT and INSERT plus three column-level updates.
- `pytest` on PostgreSQL: **442 passed, none skipped, none failed.** The API tests run as the
  application role. The first run failed four database tests; each was a fault in the test
  (it rolled back its own rows, broke a second rule, or expected a trigger where PostgreSQL's
  own foreign key or TRUNCATE rule refuses first). In every case the database had refused
  the operation. No trigger, constraint or grant was changed.
- With the test URLs blanked the same suite still passes on the in-memory stand-in: 410
  passed, 32 skipped.
- `ruff check`, `ruff format --check` and `mypy` strict are clean (86 files).
- **Not done:** no migration has been applied to `oak_misstatements`. Two requests arriving
  at the same moment have not been exercised. The live Financial Spine has not been contacted.

## Closure work on Stages 0 to 5 (D46)

Run on 5 November 2026, after the review in `docs/CLOSURE_REVIEW.md`:

- Built: the two read-only gate endpoints approved as D18; the event-kind CHECK (migration
  0010) and payload validation approved as D13; the read-only orphan-proposal report;
  `backend\requirements-lock.txt`.
- Closed from the specification: B4c, B12, F4. Found to meet it as built: N10, N14, N15.
- Investigated against the Spine's contract and left open with the findings recorded: the
  successor version (B10), changing lines (F9), withdrawal (F4, closed).
- Backend: `ruff check` and `ruff format --check` clean, `mypy` strict clean (86 files),
  `pytest` 410 passed, 32 skipped (every database test, pending O2).
  `tests\test_api_closure.py` covers the gates at their boundaries, undetermined and
  blocked-over-undetermined, read-only, the event rules, and the report on a clean
  engagement, an orphan left by a failed commit, a missing adjustment and a disputed state.
- Frontend unchanged: `eslint`, `tsc --noEmit`, `prettier --check` clean, `vitest` 5 passed.
- Not done, by instruction: no commit, no Stage 6, no Pass 2. Not run: PostgreSQL and the
  live Financial Spine.

## Stage 5 verification (D45)

Run on 5 November 2026:

- Backend: `ruff check` and `ruff format --check` clean, `mypy` strict clean (83 files),
  `pytest` 388 passed, 31 skipped (every database test, pending O2).
- `tests\test_api_conclusions.py` proves, on the stand-in and the Spine double: a
  conclusion is a new row carrying the reviewed run's figures and threshold version, with
  the reviewed run untouched; acceptance 10 (no empty conclusion or basis, at the request
  and by the row's CHECKs); no figure, role or actor accepted in the body; a stale, unknown
  or foreign reviewed run refused; acceptance 7 at 399,999.99, 400,000.00 and 400,000.01,
  and on net assets alone; the soft gate until acknowledged, a stale acknowledgement after
  a change of figures or thresholds, and `OAK_PM_GATE=hard`; acceptance 6 through raised,
  communicated and refused; no conclusion on an unknown evaluation or a disputed state;
  dev mode, a non-partner, a missing or look-alike claim, an unlisted peer; the partner
  check before any gate; a revised conclusion as another row and no row ever changed; a
  conclusion going stale; a failed commit; and the strategy trigger with and without a
  declared band.
- `tests\test_gates.py` proves which reasons block which conclusion and the strategy line.
  `tests\test_contracts.py` holds the amended route contract. `tests\test_migration_sql.py`
  proves migration 0009 from its rendered SQL; three `db`-marked tests will prove the
  CHECKs, the hard-gate trigger and append-only on PostgreSQL once a test database exists.
- Frontend unchanged: `eslint`, `tsc --noEmit`, `prettier --check` clean, `vitest` 5 passed.
- Not run: PostgreSQL and the live Financial Spine. No partner conclusion can be saved in
  any deployment until the firm's proxy presents a role claim (B9).

## Stage 4 verification (D43)

Run on 5 November 2026:

- Backend: `ruff check` and `ruff format --check` clean, `mypy` strict clean (80 files),
  `pytest` 353 passed, 28 skipped (every database test, pending O2).
- `tests\test_api_evaluation_runs.py` proves, on the stand-in and the Spine double: a run
  records the threshold version and the four aggregates equal to the live evaluation; it
  holds labels and aggregates and never one item's amount; the reassessment prompt is
  mandatory and no figure can be sent; identity is required in both modes; factual,
  judgemental, projected and classification-only items are kept apart; corrected and
  withdrawn items leave the aggregate and refused ones stay; both tests at every boundary
  of CTT, PM and OM, with a run still recorded when a gate fires; a refused item above PM
  staying in the individual test; an item material on net assets alone; no run without
  thresholds, with an unresolved effect, with an unreachable Spine or with a state the
  Spine disputes; each run keeping its own threshold version through a revision; staleness
  after a revision, a move or a new misstatement; run numbers per engagement; a run never
  changed or deleted; 404s; a failed commit recording nothing; and the evaluation answer
  keeping every earlier block.
- `tests\test_gates.py` proves the individual test on items directly.
  `tests\test_migration_sql.py` proves migration 0008 from its rendered SQL;
  `tests\test_models.py` pins the row's columns; four `db`-marked tests will prove the
  database rules on PostgreSQL once a test database exists.
- Frontend unchanged: `eslint`, `tsc --noEmit`, `prettier --check` clean, `vitest` 5 passed.
- Not run: PostgreSQL and the live Financial Spine. Not built: the conclusion (Stage 5),
  the evaluation screen (Stage 6), the prior-period carry-forward (Pass 2).

## Stage 3 safety verification (D42)

Run on 5 November 2026:

- **History.** PostgreSQL refuses UPDATE, DELETE and TRUNCATE of `misstatement`,
  `misstatement_version`, `misstatement_line_class` and `event` for every role, by the
  triggers of migrations 0002 to 0004 over the function of 0001; the application role holds
  SELECT and INSERT only. No migration was added: `tests\test_migration_sql.py` proves from
  the rendered SQL that the protection exists and that nothing later weakens it. The
  application now refuses the same statements itself (`models\guard.py`), proven on the
  stand-in by `tests\test_stage3_safety.py`.
- **Two defects found and fixed.** A commit the database refused was reported to the client
  as 201; it is now a 503 on every write. A real database refusal at flush during a move
  produced a 500 instead of the intended 503.
- **Retry.** With the commit failing after the Spine decided, for each of corrected,
  refused and withdrawn: the client gets 503; the Spine holds one decision; nothing is
  recorded here; the disagreement is reported and blocks sign-off; the retry records the
  state with `decided_now: false`, one decision call in total, one adjustment, and the
  posting applied exactly once.
- **Concurrency.** A request made to read stale versions cannot create a duplicate version
  or a second decision. The row lock that makes this case unreachable on PostgreSQL has
  never run.
- Backend: `ruff check` and `ruff format --check` clean, `mypy` strict clean (76 files),
  `pytest` 325 passed, 24 skipped (every database test, pending O2).

## B2, B8 and B9 — final status, 4 November 2026

Three senses are kept apart: **code complete** (built and tested here), **interim
assumption** (an accounting or policy reading this module uses and declares, not a
decision), and **pending externally** (a CA confirmation or an integration nobody here
can supply).

| Issue | Code complete | Interim assumption | Pending externally |
|---|---|---|---|
| B2 | Classification-only items proposed to the Spine as `reclass`, listed in the schedule and the aggregate at nil with their gross size and `classification_only` flag; an unresolved line ends the verdict (D37, D40) | "Classification only" needs nil net-assets effect as well as nil profit effect | CA confirmation of that reading; qualitative evaluation (Pass 2) |
| B8 | Aggregate gross and net, profit and net assets, with and without projected items and by type; hard and soft gates at exact OM and PM; indeterminate on unresolved items; `OAK_PM_GATE=hard` blocks; the acknowledgement goes stale on changed figures or threshold; the write-path dependency `sign_off_open` with a contract test that fails any future sign-off route lacking it (D38, D40) | Projected amounts count, always disclosed | CA confirmation of that policy; the conclusion write (Stage 4); no Opinion module exists |
| B9 | Partner-only action enforced and failing closed: dev mode, no configuration, no listed proxy, unlisted peer, missing, blank, duplicated, look-alike or non-partner claim, role in the body; contract test for every partner-only route (D39, D40) | None | The firm's proxy and identity provider presenting the claim (O1) and naming the partner value, until which partner actions are unavailable; the firm's policy for the actions the spec leaves to anyone |

Tests: `tests\test_gates.py`, `tests\test_api_evaluation.py`, `tests\test_contracts.py`,
`tests\test_identity.py`, `tests\test_config.py`, `tests\test_authorisation.py`,
`tests\test_api_misstatements.py` (D37 regressions), `tests\test_spine_kind.py`,
`tests\test_fake_spine.py`. Backend: `ruff check` and `ruff format --check` clean, `mypy`
strict clean (68 files), `pytest` 251 passed, 18 skipped (every database test, pending O2).
Frontend unchanged: `eslint`, `tsc --noEmit`, `prettier --check` clean, `vitest` 5 passed.
Not verified anywhere: PostgreSQL and the live Financial Spine. Not built: any screen, the
conclusion, the strategy trigger (B5), the state transitions (Stage 3).

## Final review of Features 1 and 2 — 4 November 2026

A read of the code against `docs/MISSTATEMENTS_ROLLUP.md`, not of the earlier reports.

- Fixed: the Spine PM cross-check answered `not_pinned` for a threshold set while the
  engagement was unpinned even after the engagement was pinned; it now answers
  `pinned_version_changed` whichever way the pin moved, with a test for both directions.
  The threshold history answer carried a reduced `authorisation` block without the identity
  mode; it now carries the same block as every other answer. Two docstrings still called
  B3 and B13 pending.
- Backend: `ruff check` and `ruff format --check` clean, `mypy` strict clean (61 files),
  `pytest` 201 passed, 18 skipped (every database test, pending O2).
- Frontend: `eslint` clean, `tsc --noEmit` clean, `prettier --check` clean, `vitest` 5
  passed. The frontend is still the Stage 0 shell; the screens are Stage 6.
- Not verified anywhere: PostgreSQL behaviour (triggers, grants, CHECKs, deferred key) and
  the live Financial Spine. Every API test runs on the in-memory stand-in and the Spine
  double. The migrations are proven from their rendered SQL only.
- Code-level complete: Feature 1 (the record over the Spine, double entry, effects,
  snapshot, drift, types, references, identity, append-only) and Feature 2 (thresholds,
  CTT, PM below OM, versions, recompute, bands and boundaries, Spine PM cross-check, read by
  id, identity). Still open, by design and documented: B2 (classification-only items are
  refused), B7's three CA confirmations, B4's three firm decisions, B8 (Stage 5), B9 (no
  role enforced), B1, B10, B12, F3, F4, F9, O1, O2.

## Authorisation verification (D36)

Run on 4 November 2026:

- `tests\test_authorisation.py` proves every write refuses without an identity and every
  read works; the acting identity lands on the engagement, each threshold version, the
  recompute event and the misstatement, and earlier rows keep their own actors; a body that
  names an actor is refused on every write route; header mode records the proxy's identity
  and refuses a missing, blank or duplicated header; every answer declares `enforced: false`;
  and only a proxy identity in production is production grade. `tests\test_migration_sql.py`
  proves 0006 freezes the engagement's audit columns and narrows the app role's grant; two
  `db`-marked tests will prove the behaviour on PostgreSQL once a test database exists.
- Not enforced, and declared so: any role or permission check.

## PM-below-OM verification (D34)

Run on 4 November 2026:

- Backend: `ruff check` and `ruff format --check` clean, `mypy` strict clean (58 files),
  `pytest` 188 passed, 16 skipped (the database tests, pending O2, now including the
  `ck_threshold_pm_below_om` rule).
- `tests\test_api_thresholds.py` proves a PM a paisa below OM is accepted, PM equal to or
  above OM is refused with SA 320 paragraph 9 named and nothing written (no version, no
  event), and a refused revision leaves the history, the current version and the trail
  exactly as they were while a later valid revision still gets the next number.
  `tests\test_migration_sql.py` proves 0005 adds the CHECK by ALTER and 0003 is unchanged.
- Not run: migration 0005 against any database.

## Banding verification (D33)

Run on 4 November 2026:

- Backend: `ruff check` and `ruff format --check` clean, `mypy` strict clean (57 files),
  `pytest` 183 passed, 15 skipped (the database tests, pending O2).
- `tests\test_banding.py` proves the literal boundaries (below CTT, exactly CTT, exactly PM,
  a paisa above PM), the inclusive aggregate gates, both effects banded separately with the
  higher band winning, no band on unresolved effects, classification-only items trivial on
  amount, and the range check; two hypothesis sweeps cover every amount and every pair of
  effects. `tests\test_api_misstatements.py` repeats the boundaries and the differing-effects
  case through the Spine double. `tests\test_api_thresholds.py` demonstrates acceptance 2:
  a misstatement's band moves from clearly trivial to accumulated to individually
  significant as the thresholds are revised, with the recompute events recorded.
- Not run: the real Financial Spine.

## Classification snapshot verification (D32)

Run on 4 November 2026:

- Backend: `ruff check` and `ruff format --check` clean, `mypy` strict clean (57 files),
  `pytest` 168 passed, 15 skipped (the database tests, pending O2, now including the
  snapshot table's append-only rule).
- Six regressions in `tests\test_api_misstatements.py` against the Spine double, which can
  now remap a ledger, retire or move a head under a new tree version, and re-key a ledger
  between reads: a remapped ledger leaves an old misstatement's effects unchanged; the drift
  is reported with the effects the current classification would give; a changed tree does
  not alter old calculations; a new version receives its own snapshot and the old one is
  kept; an unmatched line gives unresolved effects; and the snapshot table holds no amount
  (`tests\test_models.py`, `tests\test_migration_sql.py`).
- Not run: the real Financial Spine.

## Stage 2 verification

Run on 4 November 2026:

- Backend: `ruff check` and `ruff format --check` clean, `mypy` strict clean (55 files),
  `pytest` 132 passed, 14 skipped. The skipped tests are the database tests
  (`test_db_foundation.py` 3, `test_db_rules.py` 11), with the reason shown, because no test
  database exists yet (pending O2).
- After the Feature 2 verification, six fixes (D30): threshold versions are numbered and the
  history ordered by number; events are ordered by an insertion sequence; the Spine PM
  reading at set time carries a status instead of an ambiguous null; the cross-check is
  against the recorded Spine version and reports a changed pin; a PostgreSQL CHECK ties the
  stored CTT to PM times the fraction; a deferred trigger requires a successor to be a later
  version of the same engagement; and a test proves a superseded version is left exactly as
  set. The two ordering tests were run thirty times in a row and passed every time.
- The threshold and event API tests ran on the in-memory stand-in (D24). They prove
  validation, the absence of a default fraction, the paisa rounding, supersession, the
  recompute event and its payload, the Spine PM cross-check in every state, the pending band
  on misstatements, and the authorisation notice. They do not prove the supersede-once
  trigger, the successor trigger, the CTT consistency CHECK, the column-level grant, the
  partial unique index, the identity sequence or the deferred foreign key on PostgreSQL;
  `tests\test_migration_sql.py` proves migration 0003 says the right thing and the
  `db`-marked tests in `tests\test_db_rules.py` will prove the behaviour once
  `oak_misstatements_test` exists.
- Frontend: unchanged since Stage 0.
- Not run: `scripts\db\*.sql`, any Alembic command against a database, any connection to
  any database, the real Financial Spine.

## Stage 1 verification

Run on 4 November 2026:

- Backend: `ruff check` and `ruff format --check` clean, `mypy` strict clean (46 files),
  `pytest` 105 passed, 8 skipped. The skipped tests are the database tests (`test_db_foundation.py`,
  `test_db_rules.py`), with the reason shown, because no test database exists yet (pending O2).
- After the read-only verification, four fixes with their tests: a database failure after
  the Spine accepted a proposal now names the orphan adjustment and the database's own error
  in the answer and the log, whatever the error class (D22); a Spine error during a read is
  reported as the engagement's link status, never leaked as a 409 or 422; the engagement
  list reports a stored link as `recorded`, never `verified`, because it does not ask the
  Spine; and `tests\test_models.py` pins that the only money columns in this module are the
  judgemental range (spec section 1).
- The API tests ran on the in-memory stand-in (architecture D24): they prove the request
  validation, the Spine calls and their order, the record and its versions, the references,
  and every refusal. They do not prove the PostgreSQL triggers, grants or the money domain;
  `tests\test_migration_sql.py` proves the migration's SQL says the right thing, and the
  `db`-marked tests will prove the behaviour once `oak_misstatements_test` exists.
- Frontend: unchanged since Stage 0.
- Not run: `scripts\db\*.sql`, any Alembic command against a database, any connection to
  any database, the real Financial Spine.

## Stage 0 verification

Run on 4 November 2026:

- Backend: `ruff check` and `ruff format --check` clean, `mypy` strict clean (19 files),
  `pytest` 35 passed, 3 skipped. The skipped tests are the database tests, with the reason
  shown, because no test database exists yet. The API was also started on a real socket on
  port 8003 and answered the health check with the no-store headers.
- Frontend: `npm run lint`, `npm run format` and `npm run typecheck` clean, `npm test`
  5 passed in 2 files, under Node 22 through fnm.
- Not run: `scripts\db\*.sql`, any Alembic command against a database, any connection to
  any database.

## What is deliberately not built yet

- The `qualitative` table (Stage 8, D59) and the `prior_period` table with
  `evaluation.py_carried` (Stage 9, D61) now exist, and so do the TCWG extract (Stage
  10, D62) and the written representation attachment (Stage 11, D63). The rest of Pass 2
  does not: intake from agent runs and review notes, Sampling, and the generated binder
  paper.
- No edit after raising (F9), no Opinion hand-off (no such module exists). Withdrawal is
  built on an interim treatment in the Spine (B1).
- Of the screens (Stage 6), the engagement list (D47), the schedule (D48), the
  misstatement detail with its moves (D49) and the evaluation (D50) exist, were reviewed
  together (D51), and were completed by the closure work (D52): creating an engagement,
  recording a misstatement, thresholds, the Financial Spine link and reconciliation, the
  event trail, and the partner's two forms. Nothing recorded is ever edited from a screen:
  a misstatement moves by a new version, thresholds by a new version, a conclusion by a new
  row. Still not built: a way to pick a ledger or a Schedule III head when recording a
  misstatement, since the backend has no route that lists them (register S13). The
  partner's two forms can be used only where a partner can be named (B9a, O1).

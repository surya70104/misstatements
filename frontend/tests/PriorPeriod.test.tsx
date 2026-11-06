// Prior-period uncorrected misstatements on the evaluation screen (SA 450 paragraph 11(b);
// spec sections 4.1 and 10.3; acceptance 5; backend D61): each carried item with its
// current-period and its cumulative effect side by side, the totals apart from the current
// year's and together with it both ways, and the two writes the panel sends. Every answer
// and every refusal below is the backend's real one, captured by
// backend/tests/test_frontend_fixtures.py as one engagement moved on.
import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { EvaluationPage } from '../src/pages/EvaluationPage'
import {
  clearNoRun,
  evaluationAnswers,
  evaluationAnswersInTurn,
  type Snapshot,
} from './evaluationFixtures'
import { answered, deferred, failApi, inTurn, mockApi, refusal, requested, sent } from './mockApi'
import {
  afterRemoval,
  carried,
  listing,
  none,
  reachesPm,
  recorded,
  recordPath,
  refusals,
  removalPath,
  removed,
  revised,
  withRun,
} from './priorPeriodFixtures'

afterEach(() => {
  vi.unstubAllGlobals()
})

async function open(snapshot: Snapshot, answers: Record<string, unknown> = {}) {
  mockApi({ ...evaluationAnswers(snapshot), ...answers })
  const view = render(<EvaluationPage id={snapshot.engagement.id} />)
  await screen.findByRole('heading', { level: 1 })
  return view
}

function panel(): HTMLElement {
  return screen.getByRole('region', { name: 'Prior-period uncorrected misstatements' })
}

function itemsTable(): HTMLElement {
  return within(panel()).getByRole('table', { name: /^Prior-period items carried forward/ })
}

function summaryTable(): HTMLElement {
  return within(panel()).getByRole('table', { name: /^The current year's aggregate/ })
}

function cells(table: HTMLElement, row: RegExp): HTMLElement[] {
  return within(within(table).getByRole('row', { name: row })).getAllByRole('cell')
}

function posts(): string[] {
  return requested().filter((request) => request.startsWith('POST'))
}

function gets(): string[] {
  return requested().filter((request) => request.startsWith('GET'))
}

function fill(label: RegExp, value: string) {
  fireEvent.change(within(panel()).getByRole('textbox', { name: label }), { target: { value } })
}

const TYPED = {
  description: 'Rent for March of the prior year not accrued',
  prior_period: 'FY 2024-25',
  source_ref: 'PY schedule M-4',
  current_profit_before_tax: '50000.00',
  current_net_assets: '0',
  cumulative_profit_before_tax: '0.00',
  cumulative_net_assets: '-0.50',
  basis: 'Accrual of the prior year reversed in April; see PY E-4.2',
}

function fillRecordForm() {
  fill(/^What it is/, `  ${TYPED.description} `)
  fill(/^Prior period/, TYPED.prior_period)
  fill(/^Source reference/, TYPED.source_ref)
  fill(/^Current-period effect on profit before tax/, TYPED.current_profit_before_tax)
  fill(/^Current-period effect on net assets/, TYPED.current_net_assets)
  fill(/^Cumulative effect on profit before tax/, TYPED.cumulative_profit_before_tax)
  fill(/^Cumulative effect on net assets/, ` ${TYPED.cumulative_net_assets} `)
  fill(/^Basis of the effects/, TYPED.basis)
}

function openRecordForm() {
  fireEvent.click(within(panel()).getByRole('button', { name: 'Record a prior-period item' }))
}

function confirm(name: string): HTMLElement {
  return within(panel()).getByRole('button', { name })
}

// ---- nothing carried ----

test('with nothing carried the panel says so and offers to record an item', async () => {
  await open(none)
  expect(panel()).toHaveTextContent('No prior-period item is carried forward on this engagement.')
  expect(within(panel()).queryByRole('table')).not.toBeInTheDocument()
  expect(within(panel()).getByRole('button', { name: 'Record a prior-period item' })).toBeEnabled()
  // Nothing is asked for until the form is opened.
  expect(within(panel()).queryByRole('form')).not.toBeInTheDocument()
  expect(within(panel()).queryByRole('textbox')).not.toBeInTheDocument()
  expect(panel()).toHaveTextContent(
    "The gates and the sign-off decision test the current year's aggregate.",
  )
})

test('an engagement of Pass 1 shows the same empty panel', async () => {
  await open(clearNoRun)
  expect(clearNoRun.evaluation.prior_period.items).toEqual([])
  expect(panel()).toHaveTextContent('No prior-period item is carried forward on this engagement.')
})

// ---- acceptance 5: the items, their two effects side by side ----

test('each carried item shows its current-period and its cumulative effect side by side', async () => {
  await open(carried)
  expect(panel()).toHaveTextContent('2 prior-period items carried forward.')
  const table = itemsTable()
  // The two effects are column groups of the same table, each over profit and net assets.
  expect(
    within(table)
      .getAllByRole('columnheader')
      .map((header) => header.textContent),
  ).toEqual([
    'Ref',
    'Prior-period item',
    'Current-period effect',
    'Cumulative effect',
    'Actions',
    'Profit before tax',
    'Net assets',
    'Profit before tax',
    'Net assets',
  ])
  // PY-1 reversed in this period: an effect on this period's profit, nothing cumulative.
  const reversed = cells(table, /^PY-1 /)
  expect(reversed[0]).toHaveTextContent('Rent for March of the prior year not accrued')
  expect(reversed[0]).toHaveTextContent('FY 2024-25 · PY schedule M-4')
  expect(reversed[0]).toHaveTextContent(
    'Basis of the effects: Accrual of the prior year reversed in April; see PY E-4.2',
  )
  expect(reversed[0]).toHaveTextContent('by manager@firm')
  expect(reversed.slice(1, 5).map((cell) => cell.textContent)).toEqual([
    '₹50,000.00',
    '₹0.00',
    '₹0.00',
    '₹0.00',
  ])
  // PY-2 still stands: nothing new on this period's profit, all of it cumulative.
  expect(
    cells(table, /^PY-2 /)
      .slice(1, 5)
      .map((cell) => cell.textContent),
  ).toEqual(['₹0.00', '-₹30,000.00', '-₹30,000.00', '-₹30,000.00'])
  // Each cell names its effect for a reader, and for the narrow layout.
  expect(reversed[1]).toHaveAttribute('data-label', 'Current period: profit before tax')
  expect(reversed[4]).toHaveAttribute('data-label', 'Cumulative: net assets')
})

test('the current year, the prior-period totals and the two together are shown apart', async () => {
  await open(carried)
  const table = summaryTable()
  const text = (row: RegExp) => cells(table, row).map((cell) => cell.textContent)
  // Current year · prior period (current-period, cumulative) · together (each basis).
  expect(text(/^Profit before tax gross/)).toEqual([
    '₹1,90,000.00',
    '₹50,000.00',
    '₹30,000.00',
    '₹2,40,000.0096.0% of PM · 60.0% of OM',
    '₹2,20,000.0088.0% of PM · 55.0% of OM',
  ])
  // Net is signed: the reversal offsets the current year's on the current-period basis.
  expect(text(/^Profit before tax net/)).toEqual([
    '-₹1,90,000.00',
    '₹50,000.00',
    '-₹30,000.00',
    '-₹1,40,000.0056.0% of PM · 35.0% of OM',
    '-₹2,20,000.0088.0% of PM · 55.0% of OM',
  ])
  expect(text(/^Net assets gross/)).toEqual([
    '₹1,90,000.00',
    '₹30,000.00',
    '₹30,000.00',
    '₹2,20,000.0088.0% of PM · 55.0% of OM',
    '₹2,20,000.0088.0% of PM · 55.0% of OM',
  ])
  expect(text(/^Net assets net/)[0]).toBe('-₹1,90,000.00')
  // Nothing reaches a line, so nothing is marked and no note is shown.
  expect(within(panel()).queryByText(/^At or above/)).not.toBeInTheDocument()
  expect(within(panel()).queryByRole('note')).not.toBeInTheDocument()
})

test('the current year’s aggregate above is unchanged by the carried items', async () => {
  await open(carried)
  const aggregate = screen.getByRole('table', {
    name: /^Aggregate uncorrected misstatements, with and without/,
  })
  expect(cells(aggregate, /^Profit before tax gross/)[0]).toHaveTextContent('₹1,90,000.00')
  expect(carried.evaluation.aggregate.profit_before_tax.gross).toBe(
    none.evaluation.aggregate.profit_before_tax.gross,
  )
  // The same items as the schedule of prior-period items lists.
  expect(carried.evaluation.prior_period.items).toEqual(listing.items)
  expect(carried.evaluation.prior_period.totals).toEqual(listing.totals)
})

test('the backend’s own explanation is shown as it was sent', async () => {
  await open(carried)
  expect(panel()).toHaveTextContent(carried.evaluation.prior_period.basis)
})

// ---- the lines: information, never a gate ----

test('a figure that reaches PM with the carried items is marked, and no gate fires on it', async () => {
  await open(reachesPm)
  const table = summaryTable()
  // The backend names the measures at or above PM; exactly those are marked.
  expect(reachesPm.evaluation.prior_period.reaches).toEqual({
    current_period: { pm: ['net_assets.gross', 'net_assets.net'], om: [] },
    cumulative: {
      pm: ['profit.gross', 'profit.net', 'net_assets.gross', 'net_assets.net'],
      om: [],
    },
  })
  const profitGross = cells(table, /^Profit before tax gross/)
  expect(profitGross[3]).toHaveTextContent('₹2,40,000.00')
  expect(profitGross[3]).not.toHaveTextContent('At or above')
  expect(profitGross[4]).toHaveTextContent('₹2,60,000.00')
  expect(profitGross[4]).toHaveTextContent('At or above PM')
  const netAssetsGross = cells(table, /^Net assets gross/)
  expect(netAssetsGross[3]).toHaveTextContent('At or above PM')
  expect(netAssetsGross[4]).toHaveTextContent('At or above PM')
  // The current year's own figure and the prior-period totals are never marked.
  for (const cell of profitGross.slice(0, 3)) expect(cell).not.toHaveTextContent('At or above')

  expect(within(panel()).getByRole('note')).toHaveTextContent(
    'With the prior-period items, a figure is at or above performance materiality on the current-period basis and the cumulative basis. The gates do not test this.',
  )
  // The gates test the current year's 1,90,000, which is below PM: both stay clear.
  expect(reachesPm.evaluation.gates.soft.status).toBe('clear')
  expect(reachesPm.evaluation.sign_off.blocked).toBe(false)
  expect(
    screen.getByRole('region', { name: 'Soft gate: performance materiality' }),
  ).toHaveTextContent('Clear')
  expect(screen.getByRole('region', { name: 'Sign-off' })).toHaveTextContent('Open')
})

// ---- evaluation runs ----

test('a run shows which prior-period items it saw, and is stale once one is revised', async () => {
  const view = await open(withRun)
  const runs = screen.getByRole('region', { name: 'Evaluation runs' })
  fireEvent.click(within(runs).getByRole('button', { name: 'Inspect run 1' }))
  expect(runs).toHaveTextContent('Prior-period items carried')
  expect(runs).toHaveTextContent('PY-1 (version 1), PY-2 (version 1)')
  expect(runs).toHaveTextContent(
    'profit before tax gross: ₹2,40,000.00 on the current-period basis, ₹2,20,000.00 on the cumulative basis',
  )
  expect(withRun.runs[0]?.py_carried?.items).toEqual([
    { ref: 'PY-1', version_no: 1 },
    { ref: 'PY-2', version_no: 1 },
  ])
  expect(withRun.evaluation.latest_run.status).toBe('current')
  view.unmount()

  await open(reachesPm)
  expect(reachesPm.evaluation.latest_run.status).toBe('stale')
  expect(screen.getByRole('region', { name: 'Evaluation runs' })).toHaveTextContent(
    'a prior-period item has been recorded, revised or removed since the latest run was recorded',
  )
  // The revision is a second version of the same item; the first is kept.
  expect(revised.history.map((entry) => [entry.ref, entry.version_no])).toEqual([
    ['PY-1', 1],
    ['PY-2', 1],
    ['PY-2', 2],
  ])
})

// ---- recording an item ----

test('an item cannot be recorded until every figure and its basis are given', async () => {
  await open(none)
  openRecordForm()
  const form = within(panel()).getByRole('form', { name: 'Record a prior-period item' })
  expect(form).toHaveTextContent('Both are your figures: the system does not compute them.')
  expect(confirm('Confirm: record item')).toBeDisabled()
  for (const box of within(form).getAllByRole('textbox')) expect(box).toBeRequired()

  fillRecordForm()
  expect(confirm('Confirm: record item')).toBeEnabled()

  // A blank basis, a figure that is not an amount, or one with three decimals: not sent.
  fill(/^Basis of the effects/, '   ')
  expect(confirm('Confirm: record item')).toBeDisabled()
  fill(/^Basis of the effects/, TYPED.basis)
  for (const wrong of ['', 'about 50000', '50000.005', '1e5', '50,000']) {
    fill(/^Cumulative effect on net assets/, wrong)
    expect(confirm('Confirm: record item')).toBeDisabled()
  }
  expect(
    within(panel()).getByRole('textbox', { name: /^Cumulative effect on net assets/ }),
  ).toHaveAttribute('aria-invalid', 'true')
  fireEvent.submit(form)
  expect(posts()).toEqual([])
})

test('recording sends the figures exactly as typed, then reads the evaluation again', async () => {
  await open(none, {
    ...evaluationAnswersInTurn(none, carried, inTurn),
    [recordPath(none)]: answered(201, recorded),
  })
  openRecordForm()
  fillRecordForm()
  fireEvent.click(confirm('Confirm: record item'))

  expect(await screen.findByText('Recorded: PY-1 is carried forward.')).toBeInTheDocument()
  // Exact decimal strings, signed, trimmed; never a number, and never who acts.
  expect(sent()).toEqual([
    {
      request: `POST /api/engagements/${none.engagement.id}/prior-period`,
      body: TYPED,
      contentType: 'application/json',
    },
  ])
  // The six reads are asked again, and the panel shows what the backend then holds.
  expect(gets()).toHaveLength(12)
  expect(await within(panel()).findByRole('row', { name: /^PY-1 / })).toBeInTheDocument()
  expect(within(panel()).queryByRole('form')).not.toBeInTheDocument()
})

test('a refusal is shown in the backend’s words and the form is kept', async () => {
  await open(none, {
    [recordPath(none)]: refusal(refusals.blankBasis.status, refusals.blankBasis.body),
  })
  openRecordForm()
  fillRecordForm()
  fireEvent.click(confirm('Confirm: record item'))
  const alert = await within(panel()).findByRole('alert')
  expect(alert).toHaveTextContent('The item was not recorded')
  expect(alert).toHaveTextContent('basis: String should have at least 1 character')
  expect(alert).toHaveTextContent('answered 422')
  expect(within(panel()).getByRole('textbox', { name: /^What it is/ })).toHaveValue(
    `  ${TYPED.description} `,
  )
  expect(screen.queryByText(/^Recorded: PY/)).not.toBeInTheDocument()
  // Nothing was read again: nothing changed.
  expect(gets()).toHaveLength(6)
})

test('cancelling closes the form and sends nothing', async () => {
  await open(none)
  openRecordForm()
  fillRecordForm()
  fireEvent.click(within(panel()).getByRole('button', { name: 'Cancel' }))
  expect(within(panel()).queryByRole('form')).not.toBeInTheDocument()
  expect(posts()).toEqual([])
})

test('an item goes out once, however many times it is confirmed while it is processing', async () => {
  const pending = deferred()
  await open(none, { [recordPath(none)]: pending.answer })
  openRecordForm()
  fillRecordForm()
  const form = within(panel()).getByRole('form', { name: 'Record a prior-period item' })
  fireEvent.click(confirm('Confirm: record item'))
  fireEvent.click(within(form).getByRole('button', { name: 'Recording…' }))
  fireEvent.submit(form)
  expect(posts()).toHaveLength(1)
  expect(within(form).getByRole('button', { name: 'Recording…' })).toBeDisabled()
  expect(within(form).getByRole('button', { name: 'Cancel' })).toBeDisabled()
  for (const box of within(form).getAllByRole('textbox')) expect(box).toBeDisabled()

  await act(async () => {
    pending.arrive(answered(201, recorded))
    await pending.answer
  })
  expect(await screen.findByText('Recorded: PY-1 is carried forward.')).toBeInTheDocument()
  expect(posts()).toHaveLength(1)
})

test('a backend that cannot be reached is explained, and the item can be sent again', async () => {
  await open(none)
  openRecordForm()
  fillRecordForm()
  failApi()
  fireEvent.click(confirm('Confirm: record item'))
  const alert = await within(panel()).findByRole('alert')
  expect(alert).toHaveTextContent('The backend could not be reached.')

  mockApi({ ...evaluationAnswers(carried), [recordPath(none)]: answered(201, recorded) })
  fireEvent.click(confirm('Confirm: record item'))
  expect(await screen.findByText('Recorded: PY-1 is carried forward.')).toBeInTheDocument()
})

// ---- ceasing to carry an item ----

test('an item cannot stop being carried without a reason', async () => {
  await open(carried)
  fireEvent.click(within(panel()).getByRole('button', { name: 'Stop carrying PY-1' }))
  const form = within(panel()).getByRole('form', { name: 'Stop carrying PY-1' })
  expect(form).toHaveTextContent('PY-1: Rent for March of the prior year not accrued')
  expect(form).toHaveTextContent('the item and its figures stay in the record')
  expect(
    within(form).getByRole('textbox', { name: /^Reason it is no longer carried/ }),
  ).toBeRequired()
  expect(confirm('Confirm: stop carrying')).toBeDisabled()
  fill(/^Reason it is no longer carried/, '   ')
  expect(confirm('Confirm: stop carrying')).toBeDisabled()
  fireEvent.submit(form)
  expect(posts()).toEqual([])
})

test('ceasing to carry sends the reason, and the item leaves the totals but not the record', async () => {
  const reason = "Corrected by management in this year's books; see E-9"
  await open(reachesPm, {
    ...evaluationAnswersInTurn(reachesPm, afterRemoval, inTurn),
    [removalPath(reachesPm, 'PY-1')]: answered(201, removed),
  })
  fireEvent.click(within(panel()).getByRole('button', { name: 'Stop carrying PY-1' }))
  fill(/^Reason it is no longer carried/, `  ${reason} `)
  fireEvent.click(confirm('Confirm: stop carrying'))

  expect(
    await screen.findByText('Recorded: PY-1 is no longer carried forward.'),
  ).toBeInTheDocument()
  expect(sent()).toEqual([
    {
      request: `POST /api/engagements/${reachesPm.engagement.id}/prior-period/PY-1/removal`,
      body: { reason },
      contentType: 'application/json',
    },
  ])
  expect(
    await within(panel()).findByText('1 prior-period item carried forward.'),
  ).toBeInTheDocument()
  expect(within(itemsTable()).queryByRole('row', { name: /^PY-1 / })).not.toBeInTheDocument()
  expect(within(itemsTable()).getByRole('row', { name: /^PY-2 / })).toBeInTheDocument()
  // The removing version keeps the item's figures and holds the reason.
  expect(removed.removed.map((item) => [item.ref, item.version_no, item.carried])).toEqual([
    ['PY-1', 2, false],
  ])
  expect(removed.removed[0]?.basis).toBe(reason)
  expect(removed.removed[0]?.current_period.profit_before_tax).toBe('50000.00')
  expect(removed.history.filter((entry) => entry.ref === 'PY-1')).toHaveLength(2)
})

test('an item someone else has already removed is refused in the backend’s words', async () => {
  await open(carried, {
    [removalPath(carried, 'PY-1')]: refusal(refusals.notCarried.status, refusals.notCarried.body),
  })
  fireEvent.click(within(panel()).getByRole('button', { name: 'Stop carrying PY-1' }))
  fill(/^Reason it is no longer carried/, 'Removed twice')
  fireEvent.click(confirm('Confirm: stop carrying'))
  const alert = await within(panel()).findByRole('alert')
  expect(alert).toHaveTextContent(refusals.notCarried.body.detail)
  expect(alert).toHaveTextContent('answered 409')
  expect(within(itemsTable()).getByRole('row', { name: /^PY-1 / })).toBeInTheDocument()
})

test('choosing another item starts its reason afresh', async () => {
  await open(carried)
  fireEvent.click(within(panel()).getByRole('button', { name: 'Stop carrying PY-1' }))
  fill(/^Reason it is no longer carried/, 'typed for PY-1')
  fireEvent.click(within(panel()).getByRole('button', { name: 'Stop carrying PY-2' }))
  expect(within(panel()).getByRole('form', { name: 'Stop carrying PY-2' })).toBeInTheDocument()
  expect(
    within(panel()).getByRole('textbox', { name: /^Reason it is no longer carried/ }),
  ).toHaveValue('')
})

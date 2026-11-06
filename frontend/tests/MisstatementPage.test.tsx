// The misstatement detail (spec sections 6.1 and 10.2): what the page shows. The moves are
// tested in MisstatementWorkflow.test.tsx. Every fixture is the backend's real answer
// (backend/tests/test_frontend_fixtures.py): nothing here is hand-written data.
import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import type { Misstatement } from '../src/api'
import { dateTime } from '../src/format'
import { MisstatementPage } from '../src/pages/MisstatementPage'
import {
  classificationDrift,
  classificationOnly,
  communicated,
  corrected,
  detailPath,
  raised,
  refused,
  spineDown,
  withdrawn,
} from './detailFixtures'
import notFound from './fixtures/misstatement-not-found.json'
import { failApi, mockApi, refusal, requested } from './mockApi'

afterEach(() => {
  vi.unstubAllGlobals()
})

async function open(misstatement: Misstatement) {
  mockApi({ [detailPath(misstatement)]: misstatement })
  const view = render(<MisstatementPage id={misstatement.id} />)
  await screen.findByRole('heading', { level: 1 })
  return view
}

function panel(name: string): HTMLElement {
  return screen.getByRole('region', { name })
}

/** The value shown beside a label inside a panel. */
function fact(panelName: string, label: string): HTMLElement {
  const term = within(panel(panelName)).getByText(label, { selector: 'dt' })
  const value = term.nextElementSibling
  if (!(value instanceof HTMLElement)) throw new Error(`${label} has no value`)
  return value
}

function lines(): HTMLElement {
  return screen.getByRole('table', { name: 'Dr/Cr lines with their financial classification' })
}

function lineCells(ledger: string): (string | null)[] {
  const row = within(lines()).getByRole('row', { name: new RegExp(`^${ledger} `) })
  return within(row)
    .getAllByRole('cell')
    .map((cell) => cell.textContent)
}

function history(): HTMLElement[] {
  return within(screen.getByRole('list', { name: 'State history' })).getAllByRole('listitem')
}

// ---- loading and errors ----

test('it says it is loading, then asks the backend for this one misstatement', async () => {
  mockApi({ [detailPath(raised)]: raised })
  render(<MisstatementPage id={raised.id} />)
  expect(screen.getByRole('status')).toHaveTextContent('Loading the misstatement…')
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
  expect(await screen.findByRole('heading', { level: 1, name: 'M-1' })).toBeInTheDocument()
  expect(screen.queryByText('Loading the misstatement…')).not.toBeInTheDocument()
  expect(requested()).toEqual([`GET /api/misstatements/${raised.id}`])
})

test('a misstatement that does not exist is refused in the backend’s words', async () => {
  const id = '00000000-0000-4000-8000-000000000000'
  mockApi({ [`GET /api/misstatements/${id}`]: refusal(404, notFound) })
  render(<MisstatementPage id={id} />)
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent('This misstatement could not be loaded')
  expect(alert).toHaveTextContent(notFound.detail)
  expect(alert).toHaveTextContent(`/api/misstatements/${id} answered 404`)
  expect(screen.queryByRole('heading', { level: 1 })).not.toBeInTheDocument()
  expect(screen.queryByRole('region', { name: 'Workflow actions' })).not.toBeInTheDocument()
})

test('an unreachable backend is explained, and trying again loads the misstatement', async () => {
  failApi()
  render(<MisstatementPage id={raised.id} />)
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent('The backend could not be reached.')
  mockApi({ [detailPath(raised)]: raised })
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
  expect(await screen.findByRole('heading', { level: 1, name: 'M-1' })).toBeInTheDocument()
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})

// ---- identification ----

test('the identification shows the reference, type, state, band, working paper and who raised it', async () => {
  await open(raised)
  expect(fact('Identification', 'Reference')).toHaveTextContent(/^M-1$/)
  expect(fact('Identification', 'Type')).toHaveTextContent(/^Factual$/)
  expect(fact('Identification', 'Current state')).toHaveTextContent(/^Raised$/)
  expect(fact('Identification', 'Materiality band')).toHaveTextContent('Accumulated')
  expect(fact('Identification', 'Materiality band')).toHaveTextContent(
    'Against thresholds version 1',
  )
  expect(fact('Identification', 'Description')).toHaveTextContent(/^Rent for March not accrued$/)
  expect(fact('Identification', 'Working paper reference')).toHaveTextContent(/^E-4.2$/)
  expect(fact('Identification', 'Raised from')).toHaveTextContent(/^Working paper$/)
  expect(fact('Identification', 'Raised by')).toHaveTextContent(/^senior@firm$/)
  expect(fact('Identification', 'Raised')).toHaveTextContent(dateTime(raised.created_at))
})

test('the header repeats the reference, type, state and band, and leads back to the schedule', async () => {
  await open(raised)
  const header = screen.getByRole('heading', { level: 1, name: 'M-1' }).closest('header')
  if (header === null) throw new Error('the page has no header')
  expect(within(header).getByText('Factual')).toBeInTheDocument()
  expect(within(header).getByText('Raised')).toBeInTheDocument()
  expect(within(header).getByText('Accumulated')).toBeInTheDocument()
  // The engagement the misstatement belongs to is the one the way back leads to.
  expect(screen.getByRole('link', { name: 'Back to the schedule' })).toHaveAttribute(
    'href',
    `#/engagements/${raised.engagement_id}`,
  )
  expect(screen.getByRole('link', { name: 'Schedule' })).toHaveAttribute(
    'href',
    `#/engagements/${raised.engagement_id}`,
  )
  expect(screen.getByRole('link', { name: 'Engagements' })).toHaveAttribute('href', '#/')
})

test('a judgemental item shows the auditor’s range', async () => {
  await open(refused)
  expect(fact('Identification', 'Type')).toHaveTextContent(/^Judgemental$/)
  expect(fact('Identification', 'Auditor’s range')).toHaveTextContent('₹70,000.00 to ₹1,10,000.00')
  expect(refused.banding.range_crosses_pm).toBe(false)
  expect(screen.queryByText('Range crosses PM')).not.toBeInTheDocument()
  expect(screen.queryByText('Sample')).not.toBeInTheDocument()
})

test('a projected item names its sample and projection basis', async () => {
  await open(withdrawn)
  expect(fact('Identification', 'Type')).toHaveTextContent(/^Projected$/)
  expect(fact('Identification', 'Sample')).toHaveTextContent(/^S-12$/)
  expect(fact('Identification', 'Projection basis')).toHaveTextContent(
    'Ratio of error to sample value, applied to the population',
  )
  expect(within(panel('Financial effects')).getByText(/Projected from a sample/)).toBeVisible()
  expect(screen.queryByText('Auditor’s range')).not.toBeInTheDocument()
})

test('a factual item shows neither a range nor a sample', async () => {
  await open(raised)
  expect(screen.queryByText('Auditor’s range')).not.toBeInTheDocument()
  expect(screen.queryByText('Sample')).not.toBeInTheDocument()
  expect(screen.queryByText(/Projected from a sample/)).not.toBeInTheDocument()
})

// ---- accounting details ----

test('each Dr/Cr line shows its ledger, group, classification and amount to the paisa', async () => {
  await open(raised)
  const headers = within(lines())
    .getAllByRole('columnheader')
    .map((header) => header.textContent)
  expect(headers).toEqual([
    'Ledger',
    'Group',
    'Schedule III head',
    'Statement',
    'Section',
    'Debit',
    'Credit',
  ])
  expect(lineCells('Rent')).toEqual([
    'Indirect Expenses',
    'pl.expenses.other',
    'Profit and loss',
    'Profit and loss, before tax',
    '₹60,000.00',
    '—',
  ])
  expect(lineCells('Provision for expenses')).toEqual([
    'Provisions',
    'bs.liabilities.current.provisions',
    'Balance sheet',
    'Liabilities',
    '—',
    '₹60,000.00',
  ])
  // The amounts are the ones the API sent for those lines.
  expect(raised.spine.lines.map((line) => [line.ledger_name, line.dr, line.cr])).toEqual([
    ['Rent', '60000.00', '0.00'],
    ['Provision for expenses', '0.00', '60000.00'],
  ])
})

test('the Spine’s adjustment is shown as the Spine holds it', async () => {
  await open(raised)
  expect(fact('Dr/Cr lines', 'Status')).toHaveTextContent(/^proposed$/)
  expect(fact('Dr/Cr lines', 'Kind')).toHaveTextContent(/^correction$/)
  expect(fact('Dr/Cr lines', 'Reference in the Spine')).toHaveTextContent(/^M-1$/)
  expect(fact('Dr/Cr lines', 'Gross size')).toHaveTextContent(/^₹60,000.00$/)
  expect(fact('Dr/Cr lines', 'Decided by')).toHaveTextContent(/^—$/)
  expect(within(panel('Dr/Cr lines')).queryByText('Decision note')).not.toBeInTheDocument()
})

test('a decided adjustment shows the Spine’s decision and its note', async () => {
  await open(corrected)
  expect(fact('Dr/Cr lines', 'Status')).toHaveTextContent(/^accepted$/)
  expect(fact('Dr/Cr lines', 'Decided by')).toHaveTextContent(corrected.spine.decided_by ?? '')
  expect(fact('Dr/Cr lines', 'Decision note')).toHaveTextContent(
    'M-1 corrected: accepted by manager@firm in the Misstatements Rollup',
  )
})

// ---- financial effects ----

test('both effects are shown with the backend’s explanation of each', async () => {
  await open(raised)
  const effects = within(panel('Financial effects'))
  const pbt = effects.getByRole('heading', { name: 'Effect on profit before tax' }).parentElement
  const na = effects.getByRole('heading', { name: 'Effect on net assets' }).parentElement
  expect(pbt).toHaveTextContent('-₹60,000.00')
  expect(pbt).toHaveTextContent('Accumulated')
  expect(pbt).toHaveTextContent(raised.effects?.profit_basis ?? 'missing')
  expect(na).toHaveTextContent('-₹60,000.00')
  expect(na).toHaveTextContent(raised.effects?.net_assets_basis ?? 'missing')
  expect(raised.effects?.profit_before_tax).toBe('-60000.00')
  // The band's explanation is the backend's too.
  expect(effects.getByText(raised.band_basis ?? 'missing')).toBeInTheDocument()
})

test('the effect on each caption is listed as the backend computed it', async () => {
  await open(raised)
  const captions = screen.getByRole('table', {
    name: 'Effect on each Schedule III caption, debit positive',
  })
  const rows = within(captions)
    .getAllByRole('row')
    .slice(1)
    .map((row) => [...row.children].map((cell) => cell.textContent))
  expect(rows).toEqual([
    ['pl.expenses.other', 'Profit and loss', '₹60,000.00'],
    ['bs.liabilities.current.provisions', 'Balance sheet', '-₹60,000.00'],
  ])
})

test('a classification-only item shows nil effects and says what it is, in the backend’s words', async () => {
  await open(classificationOnly)
  const effects = within(panel('Financial effects'))
  expect(
    effects.getByRole('heading', { name: 'Effect on profit before tax' }).parentElement,
  ).toHaveTextContent('₹0.00')
  expect(
    effects.getByRole('heading', { name: 'Effect on net assets' }).parentElement,
  ).toHaveTextContent('₹0.00')
  expect(effects.getByText('Classification only')).toBeInTheDocument()
  expect(effects.getByText(classificationOnly.band_basis ?? 'missing')).toBeInTheDocument()
  expect(classificationOnly.band_basis).toContain('reclassification')
  expect(fact('Dr/Cr lines', 'Kind')).toHaveTextContent(/^reclass$/)
  expect(fact('Dr/Cr lines', 'Gross size')).toHaveTextContent(/^₹20,000.00$/)
})

test('when the Spine classifies every line as it did at raising, the page says so', async () => {
  await open(classificationOnly)
  expect(classificationOnly.classification?.drift).toEqual([])
  expect(
    screen.getByText('The Financial Spine classifies every line the same way now.'),
  ).toBeInTheDocument()
  expect(screen.queryByText(/now classifies/)).not.toBeInTheDocument()
})

test('a later reclassification in the Spine is disclosed and does not change the effects', async () => {
  await open(classificationDrift)
  const effects = within(panel('Financial effects'))
  expect(
    effects.getByText('The Financial Spine now classifies 1 ledger differently.'),
  ).toBeInTheDocument()
  expect(
    effects.getByText(
      'Provision for expenses: bs.liabilities.current.provisions (Liabilities) when raised, bs.liabilities.shareholders_funds.reserves.general (Equity) now.',
    ),
  ).toBeInTheDocument()
  expect(effects.getByText(/On the current classification the effects would be/)).toHaveTextContent(
    'On the current classification the effects would be ₹0.00 on profit before tax and -₹20,000.00 on net assets.',
  )
  // The effects themselves are still the ones recorded at raising.
  expect(classificationDrift.effects?.net_assets).toBe('0.00')
  expect(
    effects.getByRole('heading', { name: 'Effect on net assets' }).parentElement,
  ).toHaveTextContent('₹0.00')
  expect(
    screen.queryByText('The Financial Spine classifies every line the same way now.'),
  ).not.toBeInTheDocument()
})

// ---- figures the backend could not give ----

test('when the Spine cannot be read, lines, effects and band are disclosed as unavailable', async () => {
  await open(spineDown)
  expect(spineDown.effects).toBeNull()
  expect(spineDown.spine.lines).toEqual([])
  expect(panel('Dr/Cr lines')).toHaveTextContent('The Dr/Cr lines are not available.')
  expect(panel('Dr/Cr lines')).toHaveTextContent(
    'the Financial Spine cannot be reached for the balances',
  )
  expect(panel('Financial effects')).toHaveTextContent('The effects are not available.')
  expect(panel('Financial effects')).toHaveTextContent('Not banded')
  expect(panel('Financial effects')).toHaveTextContent(
    'no band: the Financial Spine could not be read, so there are no effects to band',
  )
  expect(fact('Identification', 'Materiality band')).toHaveTextContent('Not banded')
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
  // Nothing is shown as an amount, least of all as nil.
  expect(screen.queryByText(/₹/)).not.toBeInTheDocument()
  // What the record itself holds is still shown.
  expect(fact('Identification', 'Current state')).toHaveTextContent(/^Communicated$/)
  expect(history()).toHaveLength(2)
  expect(panel('State history')).toHaveTextContent(
    'The Financial Spine could not be read, so this state could not be compared with the adjustment it holds.',
  )
})

test('a state the Spine agrees with carries no warning', async () => {
  await open(corrected)
  expect(corrected.state_consistency.consistent).toBe(true)
  expect(screen.queryByText(/differs from the Financial Spine/)).not.toBeInTheDocument()
  expect(screen.queryByText(/could not be compared/)).not.toBeInTheDocument()
})

// ---- workflow history ----

test('the history lists every move, who made it and when, oldest first', async () => {
  await open(corrected)
  const versions = corrected.versions ?? []
  expect(versions.map((version) => version.state)).toEqual(['raised', 'communicated', 'corrected'])
  const entries = history()
  expect(entries).toHaveLength(3)

  expect(entries[0]).toHaveTextContent('Raised')
  expect(entries[0]).toHaveTextContent('by senior@firm')
  expect(entries[0]).toHaveTextContent('version 1')
  expect(entries[1]).toHaveTextContent('Communicated')
  expect(entries[1]).toHaveTextContent('by manager@firm')
  expect(entries[1]).toHaveTextContent('version 2')
  expect(entries[2]).toHaveTextContent('Corrected')
  expect(entries[2]).toHaveTextContent('by manager@firm')
  expect(entries[2]).toHaveTextContent('version 3')

  // Each entry carries the time of its own move.
  const times = entries.map((entry) => entry.querySelector('time')?.getAttribute('datetime'))
  expect(times).toEqual([
    versions[0]?.created_at,
    versions[1]?.communicated_at,
    versions[2]?.decided_at,
  ])
  expect(entries[2]).toHaveTextContent(dateTime(versions[2]?.decided_at))
})

test('a misstatement just raised has one entry', async () => {
  await open(raised)
  expect(history()).toHaveLength(1)
  expect(history()[0]).toHaveTextContent('Raised')
  expect(history()[0]).toHaveTextContent('by senior@firm')
})

test('a refusal shows management’s reason', async () => {
  await open(refused)
  const entries = history()
  expect(entries).toHaveLength(3)
  expect(entries[2]).toHaveTextContent('Refused')
  expect(entries[2]).toHaveTextContent('by manager@firm')
  expect(entries[2]).toHaveTextContent(
    'Reason for refusal: Management considers the useful life appropriate',
  )
  // The reason belongs to the move that carried it, not to the earlier ones.
  expect(entries[0]).not.toHaveTextContent('Reason')
  expect(entries[1]).not.toHaveTextContent('Reason')
})

test('a withdrawal shows the auditor’s reason', async () => {
  await open(withdrawn)
  const entries = history()
  expect(entries[2]).toHaveTextContent('Withdrawn')
  expect(entries[2]).toHaveTextContent('by senior@firm')
  expect(entries[2]).toHaveTextContent(
    'Reason for withdrawal: Sample re-performed: the errors were recorded in the correct period',
  )
  expect(entries[2]).not.toHaveTextContent('Reason for refusal')
})

// ---- the record cannot be edited ----

test('nothing on the page edits the record: no field is offered until a move is chosen', async () => {
  for (const misstatement of [raised, communicated, corrected, refused, withdrawn]) {
    const view = await open(misstatement)
    expect(screen.queryAllByRole('textbox')).toEqual([])
    expect(screen.queryByRole('button', { name: /edit|delete|save|change/i })).toBeNull()
    view.unmount()
  }
})

test('opening another misstatement loads that one', async () => {
  mockApi({ [detailPath(raised)]: raised, [detailPath(refused)]: refused })
  const view = render(<MisstatementPage id={raised.id} />)
  expect(await screen.findByRole('heading', { level: 1, name: 'M-1' })).toBeInTheDocument()
  view.rerender(<MisstatementPage id={refused.id} />)
  expect(await screen.findByRole('heading', { level: 1, name: 'M-2' })).toBeInTheDocument()
  expect(fact('Identification', 'Current state')).toHaveTextContent(/^Refused$/)
})

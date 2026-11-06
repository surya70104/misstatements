// The schedule of misstatements (spec sections 6.1 and 10.1). The fixtures are the backend's
// real answers (backend/tests/test_frontend_fixtures.py): nothing here is hand-written data.
import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import type { Engagement } from '../src/api'
import { SchedulePage } from '../src/pages/SchedulePage'
import notFound from './fixtures/engagement-not-found.json'
import { failApi, mockApi, refusal, requested } from './mockApi'
import {
  emptyEngagement,
  emptyEvaluation,
  emptyMisstatements,
  engagement,
  evaluation,
  misstatements,
  SCHEDULE,
  scheduleAnswers,
  spineDownEvaluation,
  spineDownMisstatements,
} from './scheduleFixtures'

afterEach(() => {
  vi.unstubAllGlobals()
})

async function open(answers: Record<string, unknown> = SCHEDULE, id = engagement.id) {
  mockApi(answers)
  const view = render(<SchedulePage id={id} />)
  await screen.findByRole('heading', { level: 1 })
  return view
}

function schedule(): HTMLElement {
  return screen.getByRole('table', { name: 'Schedule of misstatements' })
}

/** The references of the rows shown, in order. */
function shownRefs(): (string | null)[] {
  return within(schedule())
    .getAllByRole('rowheader')
    .map((header) => header.textContent)
}

function row(ref: string): HTMLElement {
  return within(schedule()).getByRole('row', { name: new RegExp(`^${ref} `) })
}

function setFilter(label: 'Band' | 'Type' | 'State', value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } })
}

// ---- loading ----

test('it says it is loading, then asks for the engagement, its misstatements and its evaluation', async () => {
  mockApi(SCHEDULE)
  render(<SchedulePage id={engagement.id} />)
  expect(screen.getByRole('status')).toHaveTextContent('Loading the schedule…')
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
  expect(await screen.findByRole('heading', { name: engagement.label })).toBeInTheDocument()
  expect(screen.queryByText('Loading the schedule…')).not.toBeInTheDocument()
  expect(requested().sort()).toEqual(
    [
      `GET /api/engagements/${engagement.id}`,
      `GET /api/engagements/${engagement.id}/evaluation`,
      `GET /api/engagements/${engagement.id}/misstatements`,
    ].sort(),
  )
})

// ---- the header (kept from part 1) ----

test('the schedule leads to the engagement’s evaluation', async () => {
  await open()
  expect(screen.getByRole('link', { name: 'Evaluation' })).toHaveAttribute(
    'href',
    `#/engagements/${engagement.id}/evaluation`,
  )
})

test('the header shows the engagement and what the backend says about its Spine link', async () => {
  await open()
  expect(screen.getByText('Schedule of misstatements', { selector: 'p' })).toBeInTheDocument()
  expect(screen.getByText('Financial Spine link verified')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Engagements' })).toHaveAttribute('href', '#/')
})

test('a Spine the backend could not verify is reported with the backend’s reason', async () => {
  const unreachable: Engagement = {
    ...engagement,
    spine: {
      ...engagement.spine,
      status: 'unreachable',
      is_locked: null,
      detail: 'the Financial Spine cannot be reached for an engagement',
    },
  }
  await open(scheduleAnswers(engagement.id, { engagement: unreachable, misstatements, evaluation }))
  expect(screen.getByText('Financial Spine unreachable')).toBeInTheDocument()
  expect(
    screen.getByText('the Financial Spine cannot be reached for an engagement'),
  ).toBeInTheDocument()
})

test('a locked Spine version is flagged', async () => {
  const locked: Engagement = { ...engagement, spine: { ...engagement.spine, is_locked: true } }
  await open(scheduleAnswers(engagement.id, { engagement: locked, misstatements, evaluation }))
  expect(screen.getByText('Version locked')).toBeInTheDocument()
})

// ---- the schedule ----

test('every misstatement of the engagement is listed, in the backend’s order', async () => {
  await open()
  expect(misstatements).toHaveLength(7)
  expect(shownRefs()).toEqual(misstatements.map((entry) => entry.ref))
  expect(shownRefs()).toEqual(['M-1', 'M-2', 'M-3', 'M-4', 'M-5', 'M-6', 'M-7'])
  expect(screen.getByRole('status')).toHaveTextContent('7 misstatements')
})

test('the columns are the ten the specification names', async () => {
  await open()
  const headers = within(schedule())
    .getAllByRole('columnheader')
    .map((header) => header.textContent)
  expect(headers).toEqual([
    'Ref',
    'Type',
    'Description',
    'Dr/Cr lines',
    'PBT effect',
    'Net assets effect',
    'Band',
    'State',
    'WP ref',
    'Raised by',
  ])
})

test('a row shows the backend’s values for every column', async () => {
  await open()
  const cells = within(row('M-1')).getAllByRole('cell')
  expect(cells.map((cell) => cell.textContent)).toEqual([
    'Factual',
    'Rent for March not accrued',
    'DrRent₹60,000.00CrProvision for expenses₹60,000.00',
    '-₹60,000.00',
    '-₹60,000.00',
    'Accumulated',
    'Communicated',
    'E-4.2',
    'senior@firm',
  ])
  // Each cell names its column, which is what a narrow screen shows beside the value.
  expect(cells.map((cell) => cell.getAttribute('data-label'))).toEqual([
    'Type',
    'Description',
    'Dr/Cr lines',
    'PBT effect',
    'Net assets effect',
    'Band',
    'State',
    'WP ref',
    'Raised by',
  ])
})

test('the Dr/Cr lines are the Spine’s, debit and credit told apart, to the paisa', async () => {
  await open()
  const lines = within(row('M-2'))
    .getAllByRole('listitem')
    .map((line) => line.textContent)
  expect(lines).toEqual(['DrAlpha Traders₹8,000.00', 'CrSales₹8,000.00'])
  // Nothing is derived: the amounts are the ones the API sent for those lines.
  const sent = misstatements.find((entry) => entry.ref === 'M-2')?.spine.lines
  expect(sent?.map((line) => [line.ledger_name, line.dr, line.cr])).toEqual([
    ['Alpha Traders', '8000.00', '0.00'],
    ['Sales', '0.00', '8000.00'],
  ])
})

test('an effect keeps its sign: a misstatement can increase profit', async () => {
  await open()
  const cells = within(row('M-2')).getAllByRole('cell')
  expect(cells[3]).toHaveTextContent('₹8,000.00')
  expect(cells[3]).not.toHaveTextContent('-')
  expect(cells[4]).toHaveTextContent('₹8,000.00')
})

test('every type, state and band the backend sent is shown in words', async () => {
  await open()
  expect(within(row('M-3')).getByText('Judgemental')).toBeInTheDocument()
  expect(within(row('M-3')).getByText('Refused')).toBeInTheDocument()
  expect(within(row('M-4')).getByText('Projected')).toBeInTheDocument()
  expect(within(row('M-4')).getByText('Raised')).toBeInTheDocument()
  expect(within(row('M-5')).getByText('Individually significant')).toBeInTheDocument()
  expect(within(row('M-5')).getByText('Corrected')).toBeInTheDocument()
  expect(within(row('M-2')).getByText('Clearly trivial')).toBeInTheDocument()
  expect(within(row('M-7')).getByText('Withdrawn')).toBeInTheDocument()
})

test('a classification-only item shows nil effects and says what it is', async () => {
  await open()
  const cells = within(row('M-6')).getAllByRole('cell')
  expect(cells[3]).toHaveTextContent('₹0.00')
  expect(cells[4]).toHaveTextContent('₹0.00')
  expect(cells[5]).toHaveTextContent('Clearly trivial')
  expect(cells[5]).toHaveTextContent('Classification only')
  expect(within(row('M-1')).queryByText('Classification only')).not.toBeInTheDocument()
})

test('a reference opens the misstatement’s detail route', async () => {
  await open()
  for (const entry of misstatements) {
    expect(within(schedule()).getByRole('link', { name: entry.ref })).toHaveAttribute(
      'href',
      `#/misstatements/${entry.id}`,
    )
  }
})

test('the running totals sit above the schedule', async () => {
  await open()
  const totals = screen.getByRole('table', { name: /Aggregate uncorrected misstatements/ })
  expect(totals.compareDocumentPosition(schedule()) & Node.DOCUMENT_POSITION_FOLLOWING).toBe(
    Node.DOCUMENT_POSITION_FOLLOWING,
  )
  expect(
    within(totals).getByRole('row', { name: /^Profit before tax gross ₹1,95,000.00/ }),
  ).toBeInTheDocument()
})

// ---- filters ----

test('the three filters offer the backend’s values', async () => {
  await open()
  const options = (label: string) =>
    within(screen.getByLabelText(label))
      .getAllByRole('option')
      .map((option) => option.textContent)
  expect(options('Band')).toEqual([
    'All bands',
    'Clearly trivial',
    'Accumulated',
    'Individually significant',
    'Not banded',
  ])
  expect(options('Type')).toEqual(['All types', 'Factual', 'Judgemental', 'Projected'])
  expect(options('State')).toEqual([
    'All states',
    'Raised',
    'Communicated',
    'Corrected',
    'Refused',
    'Withdrawn',
  ])
  expect(screen.getByRole('button', { name: 'Clear filters' })).toBeDisabled()
})

test('filtering by state shows only the misstatements in that state', async () => {
  await open()
  setFilter('State', 'raised')
  expect(shownRefs()).toEqual(['M-2', 'M-4', 'M-6'])
  expect(screen.getByRole('status')).toHaveTextContent('Showing 3 of 7 misstatements')
  setFilter('State', 'refused')
  expect(shownRefs()).toEqual(['M-3'])
  setFilter('State', 'withdrawn')
  expect(shownRefs()).toEqual(['M-7'])
})

test('filtering by type shows only the misstatements of that type', async () => {
  await open()
  setFilter('Type', 'projected')
  expect(shownRefs()).toEqual(['M-4'])
  setFilter('Type', 'judgemental')
  expect(shownRefs()).toEqual(['M-3'])
  setFilter('Type', 'factual')
  expect(shownRefs()).toEqual(['M-1', 'M-2', 'M-5', 'M-6', 'M-7'])
})

test('filtering by band uses the band the backend computed', async () => {
  await open()
  setFilter('Band', 'individually_significant')
  expect(shownRefs()).toEqual(['M-5'])
  setFilter('Band', 'clearly_trivial')
  expect(shownRefs()).toEqual(['M-2', 'M-6'])
  setFilter('Band', 'accumulated')
  expect(shownRefs()).toEqual(
    misstatements.filter((entry) => entry.band === 'accumulated').map((entry) => entry.ref),
  )
  expect(shownRefs()).toEqual(['M-1', 'M-3', 'M-4', 'M-7'])
})

test('filters combine, and clearing them shows everything again', async () => {
  await open()
  setFilter('State', 'raised')
  setFilter('Type', 'factual')
  expect(shownRefs()).toEqual(['M-2', 'M-6'])
  setFilter('Band', 'clearly_trivial')
  expect(shownRefs()).toEqual(['M-2', 'M-6'])
  expect(screen.getByRole('status')).toHaveTextContent('Showing 2 of 7 misstatements')

  fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }))
  expect(shownRefs()).toHaveLength(7)
  expect(screen.getByRole('status')).toHaveTextContent(/^7 misstatements$/)
  expect(screen.getByLabelText('State')).toHaveValue('')
  expect(screen.getByLabelText('Type')).toHaveValue('')
  expect(screen.getByLabelText('Band')).toHaveValue('')
})

test('filters that match nothing say so, and keep the filters and the totals in view', async () => {
  await open()
  setFilter('Type', 'projected')
  setFilter('State', 'corrected')
  expect(screen.queryByRole('table', { name: 'Schedule of misstatements' })).not.toBeInTheDocument()
  expect(screen.getByText('No misstatement matches these filters')).toBeInTheDocument()
  expect(screen.getByRole('status')).toHaveTextContent('Showing 0 of 7 misstatements')
  expect(screen.getByLabelText('State')).toHaveValue('corrected')
  expect(
    screen.getByRole('table', { name: /Aggregate uncorrected misstatements/ }),
  ).toBeInTheDocument()
})

test('the filters never change the totals, which are the backend’s for the whole engagement', async () => {
  await open()
  const totals = () =>
    screen.getByRole('table', { name: /Aggregate uncorrected misstatements/ }).textContent
  const before = totals()
  setFilter('State', 'corrected')
  expect(shownRefs()).toEqual(['M-5'])
  expect(totals()).toBe(before)
  expect(before).toContain('₹1,95,000.00')
  // Filtering asks the backend for nothing more.
  expect(requested()).toHaveLength(3)
})

// ---- empty ----

test('an engagement with nothing raised says so, with nil totals and no filters', async () => {
  await open(
    scheduleAnswers(emptyEngagement.id, {
      engagement: emptyEngagement,
      misstatements: emptyMisstatements,
      evaluation: emptyEvaluation,
    }),
    emptyEngagement.id,
  )
  expect(emptyMisstatements).toEqual([])
  expect(screen.getByText('No misstatements raised')).toBeInTheDocument()
  expect(screen.queryByRole('table', { name: 'Schedule of misstatements' })).not.toBeInTheDocument()
  expect(screen.queryByLabelText('State')).not.toBeInTheDocument()
  const totals = screen.getByRole('table', { name: /Aggregate uncorrected misstatements/ })
  expect(within(totals).getAllByText('₹0.00')).toHaveLength(4)
  expect(
    screen.getByText('Thresholds are not set, so there are no lines to compare with.'),
  ).toBeInTheDocument()
  // No way to raise one is offered here.
  expect(screen.queryByRole('button')).not.toBeInTheDocument()
})

// ---- figures the backend could not give ----

test('when the Spine cannot be read, nothing is shown as zero and the reason is given', async () => {
  await open(
    scheduleAnswers(engagement.id, {
      engagement,
      misstatements: spineDownMisstatements,
      evaluation: spineDownEvaluation,
    }),
  )
  expect(shownRefs()).toHaveLength(7)
  const cells = within(row('M-1')).getAllByRole('cell')
  expect(cells[2]).toHaveTextContent(
    'Not available' + 'the Financial Spine cannot be reached for the balances',
  )
  expect(cells[3]).toHaveTextContent(/^Not available$/)
  expect(cells[4]).toHaveTextContent(/^Not available$/)
  expect(cells[5]).toHaveTextContent('Not banded')
  expect(cells[5]).toHaveTextContent(
    'no band: the Financial Spine could not be read, so there are no effects to band',
  )
  // What the record itself holds is still shown.
  expect(cells[0]).toHaveTextContent('Factual')
  expect(cells[6]).toHaveTextContent('Communicated')
  expect(within(schedule()).queryByText(/₹/)).not.toBeInTheDocument()
  expect(screen.getByText(/These totals are incomplete: 5 misstatements/)).toBeInTheDocument()

  setFilter('Band', 'none')
  expect(shownRefs()).toHaveLength(7)
  setFilter('Band', 'accumulated')
  expect(screen.getByText('No misstatement matches these filters')).toBeInTheDocument()
})

// ---- errors ----

test('an engagement that does not exist is refused in the backend’s words', async () => {
  const id = '00000000-0000-4000-8000-000000000000'
  mockApi({ [`GET /api/engagements/${id}`]: refusal(404, notFound) })
  render(<SchedulePage id={id} />)
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent('This schedule could not be loaded')
  expect(alert).toHaveTextContent(notFound.detail)
  expect(alert).toHaveTextContent(`/api/engagements/${id} answered 404`)
  expect(screen.queryByRole('heading', { level: 1 })).not.toBeInTheDocument()
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
})

test('if the misstatements cannot be read, nothing partial is shown', async () => {
  mockApi({
    ...SCHEDULE,
    [`GET /api/engagements/${engagement.id}/misstatements`]: refusal(503, {
      detail: 'the database is not available',
    }),
  })
  render(<SchedulePage id={engagement.id} />)
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent('the database is not available')
  expect(alert).toHaveTextContent(`/api/engagements/${engagement.id}/misstatements answered 503`)
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
  expect(screen.queryByText(/₹/)).not.toBeInTheDocument()
})

test('if the evaluation cannot be read, the schedule is not shown without its totals', async () => {
  mockApi({
    ...SCHEDULE,
    [`GET /api/engagements/${engagement.id}/evaluation`]: refusal(500),
  })
  render(<SchedulePage id={engagement.id} />)
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent(`/api/engagements/${engagement.id}/evaluation answered 500`)
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
})

test('an unreachable backend is explained, and trying again loads the schedule', async () => {
  failApi()
  render(<SchedulePage id={engagement.id} />)
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent('The backend could not be reached.')
  expect(alert).not.toHaveTextContent('answered')

  mockApi(SCHEDULE)
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
  expect(await screen.findByRole('heading', { name: engagement.label })).toBeInTheDocument()
  expect(shownRefs()).toHaveLength(7)
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})

// ---- another engagement ----

test('opening another engagement loads that one and starts with no filters', async () => {
  const view = await open({
    ...SCHEDULE,
    ...scheduleAnswers(emptyEngagement.id, {
      engagement: emptyEngagement,
      misstatements,
      evaluation: emptyEvaluation,
    }),
  })
  setFilter('State', 'raised')
  expect(shownRefs()).toHaveLength(3)
  view.rerender(<SchedulePage id={emptyEngagement.id} />)
  expect(await screen.findByRole('heading', { name: emptyEngagement.label })).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: engagement.label })).not.toBeInTheDocument()
  expect(screen.getByLabelText('State')).toHaveValue('')
  expect(shownRefs()).toHaveLength(7)
})

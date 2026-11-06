// The evaluation screen (spec sections 4.1, 6.4, 7 and 10.3): what it shows. The two writes
// it sends are tested in EvaluationActions.test.tsx. Every fixture is the backend's real
// answer (backend/tests/test_frontend_fixtures.py): nothing here is hand-written data.
import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { dateTime } from '../src/format'
import { EvaluationPage } from '../src/pages/EvaluationPage'
import {
  clearNoRun,
  concluded,
  conclusionStale,
  empty,
  evaluationAnswers,
  hardGate,
  itemAbovePm,
  partnerAvailable,
  readPath,
  runCurrent,
  runStale,
  softGate,
  spineDown,
  strategyRecorded,
  strategyRequired,
  twoConclusions,
  twoRuns,
  type Snapshot,
} from './evaluationFixtures'
import notFound from './fixtures/engagement-not-found.json'
import { failApi, mockApi, refusal, requested } from './mockApi'

afterEach(() => {
  vi.unstubAllGlobals()
})

async function open(snapshot: Snapshot) {
  mockApi(evaluationAnswers(snapshot))
  const view = render(<EvaluationPage id={snapshot.engagement.id} />)
  await screen.findByRole('heading', { level: 1 })
  return view
}

function panel(name: string): HTMLElement {
  return screen.getByRole('region', { name })
}

function aggregate(): HTMLElement {
  return screen.getByRole('table', {
    name: /^Aggregate uncorrected misstatements, with and without/,
  })
}

function byType(): HTMLElement {
  return screen.getByRole('table', { name: /^Gross contribution of factual/ })
}

function cells(table: HTMLElement, row: RegExp): (string | null)[] {
  return within(within(table).getByRole('row', { name: row }))
    .getAllByRole('cell')
    .map((cell) => cell.textContent)
}

function runs(): HTMLElement {
  return screen.getByRole('table', { name: 'Evaluation runs, newest first' })
}

function runRow(runNo: number): HTMLElement {
  return within(runs()).getByRole('row', {
    name: new RegExp(`^Run ${String(runNo)}(Run|Conclusion)`),
  })
}

// ---- loading and errors ----

test('it says it is loading, then asks for the six things the evaluation needs', async () => {
  mockApi(evaluationAnswers(clearNoRun))
  render(<EvaluationPage id={clearNoRun.engagement.id} />)
  expect(screen.getByRole('status')).toHaveTextContent('Loading the evaluation…')
  expect(
    await screen.findByRole('heading', { level: 1, name: clearNoRun.engagement.label }),
  ).toBeInTheDocument()
  const id = clearNoRun.engagement.id
  expect(requested().sort()).toEqual(
    [
      `GET /api/engagements/${id}`,
      `GET /api/engagements/${id}/evaluation`,
      `GET /api/engagements/${id}/evaluation/runs`,
      `GET /api/engagements/${id}/evaluation/conclusions`,
      `GET /api/engagements/${id}/gates/opinion`,
      `GET /api/engagements/${id}/gates/sign-off`,
    ].sort(),
  )
})

test('an engagement that does not exist is refused in the backend’s words', async () => {
  const id = '00000000-0000-4000-8000-000000000000'
  mockApi({ [`GET /api/engagements/${id}`]: refusal(404, notFound) })
  render(<EvaluationPage id={id} />)
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent('This evaluation could not be loaded')
  expect(alert).toHaveTextContent(notFound.detail)
  expect(alert).toHaveTextContent(`/api/engagements/${id} answered 404`)
  expect(screen.queryByRole('heading', { level: 1 })).not.toBeInTheDocument()
})

test('if any one read fails, nothing partial is shown', async () => {
  const id = clearNoRun.engagement.id
  mockApi({ ...evaluationAnswers(clearNoRun), [readPath(id, 'opinion_gate')]: refusal(500) })
  render(<EvaluationPage id={id} />)
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent(`/api/engagements/${id}/gates/opinion answered 500`)
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
  expect(screen.queryByText(/₹/)).not.toBeInTheDocument()
})

test('an unreachable backend is explained, and trying again loads the evaluation', async () => {
  failApi()
  render(<EvaluationPage id={clearNoRun.engagement.id} />)
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent('The backend could not be reached.')
  mockApi(evaluationAnswers(clearNoRun))
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
  expect(await screen.findByRole('heading', { level: 1 })).toBeInTheDocument()
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})

// ---- navigation ----

test('the page leads back to the engagement’s schedule and to the engagements', async () => {
  await open(clearNoRun)
  const id = clearNoRun.engagement.id
  expect(screen.getByRole('link', { name: 'Engagements' })).toHaveAttribute('href', '#/')
  expect(screen.getByRole('link', { name: clearNoRun.engagement.label })).toHaveAttribute(
    'href',
    `#/engagements/${id}`,
  )
  expect(screen.getByRole('link', { name: 'Back to the schedule' })).toHaveAttribute(
    'href',
    `#/engagements/${id}`,
  )
})

// ---- aggregate financial impact ----

test('the aggregate shows gross and net, on profit and on net assets, with and without projected', async () => {
  await open(clearNoRun)
  const figures = clearNoRun.evaluation.aggregate.profit_before_tax
  expect([figures.gross, figures.net]).toEqual(['195000.00', '-195000.00'])
  expect([figures.gross_without_projected, figures.net_without_projected]).toEqual([
    '150000.00',
    '-150000.00',
  ])
  expect(cells(aggregate(), /^Profit before tax gross/).slice(0, 2)).toEqual([
    '₹1,95,000.00',
    '₹1,50,000.00',
  ])
  expect(cells(aggregate(), /^Profit before tax net/).slice(0, 2)).toEqual([
    '-₹1,95,000.00',
    '-₹1,50,000.00',
  ])
  expect(cells(aggregate(), /^Net assets gross/).slice(0, 2)).toEqual([
    '₹1,95,000.00',
    '₹1,50,000.00',
  ])
  expect(cells(aggregate(), /^Net assets net/).slice(0, 2)).toEqual([
    '-₹1,95,000.00',
    '-₹1,50,000.00',
  ])
})

test('the gross contribution of each type is shown as the backend gives it', async () => {
  await open(clearNoRun)
  expect(
    within(byType())
      .getAllByRole('columnheader')
      .map((header) => header.textContent),
  ).toEqual(['Effect', 'Factual', 'Judgemental', 'Projected'])
  expect(cells(byType(), /^Profit before tax gross/)).toEqual([
    '₹60,000.00',
    '₹90,000.00',
    '₹45,000.00',
  ])
  expect(cells(byType(), /^Net assets gross/)).toEqual(['₹60,000.00', '₹90,000.00', '₹45,000.00'])
  const sent = clearNoRun.evaluation.aggregate.profit_before_tax
  expect([sent.factual_gross, sent.judgemental_gross, sent.projected_gross]).toEqual([
    '60000.00',
    '90000.00',
    '45000.00',
  ])
})

test('what was counted, left out, projected and classification-only is named', async () => {
  await open(clearNoRun)
  const text = panel('Aggregate of uncorrected misstatements')
  expect(text).toHaveTextContent(
    '4 misstatements accumulated (M-1, M-3, M-4, M-6); clearly trivial, not accumulated: M-2; not counted: M-5 (corrected).',
  )
  // Spec section 4: below the clearly-trivial threshold, not accumulated. The backend names it.
  expect(clearNoRun.evaluation.aggregate.not_accumulated).toEqual(['M-2'])
  expect(text).toHaveTextContent(
    'A misstatement below the clearly-trivial threshold stays in the schedule and is in no aggregate figure and no gate.',
  )
  expect(text).toHaveTextContent('Projected misstatements counted: M-4.')
  expect(text).toHaveTextContent('Classification only, contributing nil: M-6.')
  expect(within(text).getByText(clearNoRun.evaluation.aggregate.basis)).toBeInTheDocument()
})

// ---- materiality comparison ----

test('the three lines are shown with their amounts and the threshold version', async () => {
  await open(clearNoRun)
  expect(panel('Aggregate of uncorrected misstatements')).toHaveTextContent(
    'Against thresholds version 1: CTT ₹12,500.00 · PM ₹2,50,000.00 · OM ₹4,00,000.00',
  )
  expect(
    within(aggregate())
      .getAllByRole('columnheader')
      .map((header) => header.textContent),
  ).toEqual([
    'Effect',
    'With projected',
    'Without projected',
    '% of CTT₹12,500.00',
    '% of PM₹2,50,000.00',
    '% of OM₹4,00,000.00',
  ])
})

test('each aggregate is given as an exact percentage of CTT, PM and OM', async () => {
  await open(clearNoRun)
  // 1,95,000 against 12,500, 2,50,000 and 4,00,000; 48.75% rounds half up to 48.8%.
  expect(cells(aggregate(), /^Profit before tax gross/).slice(2)).toEqual([
    '1,560.0%',
    '78.0%',
    '48.8%',
  ])
  expect(cells(aggregate(), /^Net assets net/).slice(2)).toEqual(['1,560.0%', '78.0%', '48.8%'])
})

test('below every line, no figure is marked as reaching one', async () => {
  await open(clearNoRun)
  expect(clearNoRun.evaluation.gates.soft.fires_on).toEqual([])
  expect(screen.queryByText(/^At or above (PM|OM)$/)).not.toBeInTheDocument()
})

test('a figure the soft gate names is marked at or above PM, and only PM', async () => {
  await open(softGate)
  expect(softGate.evaluation.gates.soft.fires_on).toEqual([
    'profit.gross',
    'profit.net',
    'net_assets.gross',
    'net_assets.net',
  ])
  // Exactly at the line counts: "at or above".
  expect(cells(aggregate(), /^Profit before tax gross/)).toEqual([
    '₹2,50,000.00',
    '₹2,50,000.00',
    '2,000.0%',
    '100.0%At or above PM',
    '62.5%',
  ])
  expect(within(aggregate()).getAllByText('At or above PM')).toHaveLength(4)
  expect(within(aggregate()).queryByText('At or above OM')).not.toBeInTheDocument()
})

test('a figure the hard gate names is marked at or above OM', async () => {
  await open(hardGate)
  expect(cells(aggregate(), /^Profit before tax gross/)).toEqual([
    '₹4,00,000.00',
    '₹2,00,000.00',
    '3,200.0%',
    '160.0%At or above PM',
    '100.0%At or above OM',
  ])
  expect(within(aggregate()).getAllByText('At or above OM')).toHaveLength(4)
})

test('the marks follow the backend’s gates, not a comparison made on the screen', async () => {
  // The same figures, but the backend's gates name nothing: nothing is marked.
  const silent: Snapshot = {
    ...hardGate,
    evaluation: {
      ...hardGate.evaluation,
      gates: {
        ...hardGate.evaluation.gates,
        hard: { ...hardGate.evaluation.gates.hard, fires_on: [] },
        soft: { ...hardGate.evaluation.gates.soft, fires_on: ['profit.gross'] },
      },
    },
  }
  await open(silent)
  expect(within(aggregate()).queryByText('At or above OM')).not.toBeInTheDocument()
  expect(within(aggregate()).getAllByText('At or above PM')).toHaveLength(1)
  expect(cells(aggregate(), /^Profit before tax gross/)[4]).toBe('100.0%')
})

test('with no thresholds the amounts are shown and no percentage is invented', async () => {
  await open(empty)
  expect(empty.evaluation.threshold).toBeNull()
  expect(panel('Aggregate of uncorrected misstatements')).toHaveTextContent(
    'Thresholds are not set, so there are no lines to compare the aggregate with.',
  )
  expect(cells(aggregate(), /^Profit before tax gross/)).toEqual(['₹0.00', '₹0.00', '—', '—', '—'])
  expect(screen.queryByText(/%$/)).not.toBeInTheDocument()
  expect(panel('Aggregate of uncorrected misstatements')).toHaveTextContent(
    '0 misstatements accumulated.',
  )
})

// ---- incomplete and unresolved ----

test('an aggregate the backend marks incomplete is flagged, naming what is missing', async () => {
  await open(spineDown)
  expect(spineDown.evaluation.aggregate.complete).toBe(false)
  expect(panel('Aggregate of uncorrected misstatements')).toHaveTextContent(
    'This aggregate is incomplete: 5 misstatements could not be aggregated (M-1, M-2, M-3, M-4, M-6). The figures cover the others only.',
  )
})

test('a complete aggregate carries no warning', async () => {
  await open(clearNoRun)
  expect(screen.queryByText(/This aggregate is incomplete/)).not.toBeInTheDocument()
})

// ---- gates ----

test('when nothing fires every gate says so', async () => {
  await open(clearNoRun)
  expect(panel('Opinion gate')).toHaveTextContent('Open')
  expect(panel('Opinion gate')).toHaveTextContent('The backend gives no reason against it.')
  expect(panel('Sign-off')).toHaveTextContent('Open')
  expect(panel('Hard gate: overall materiality')).toHaveTextContent('Clear')
  expect(panel('Hard gate: overall materiality')).toHaveTextContent('₹4,00,000.00')
  expect(panel('Hard gate: overall materiality')).toHaveTextContent('₹1,95,000.00')
  expect(panel('Soft gate: performance materiality')).toHaveTextContent('Clear')
  expect(panel('Soft gate: performance materiality')).toHaveTextContent(
    'Firm setting for this gate: soft.',
  )
  expect(panel('Soft gate: performance materiality')).toHaveTextContent('Not required')
  expect(panel('Individual items')).toHaveTextContent('None')
  // What each gate covers is the backend's description.
  expect(within(panel('Opinion gate')).getByText(clearNoRun.opinion_gate.scope)).toBeInTheDocument()
  expect(within(panel('Sign-off')).getByText(clearNoRun.sign_off_gate.scope)).toBeInTheDocument()
})

test('the soft gate firing blocks sign-off and asks for the partner, in the backend’s words', async () => {
  await open(softGate)
  const soft = panel('Soft gate: performance materiality')
  expect(soft).toHaveTextContent('Fires')
  expect(soft).toHaveTextContent(
    'At or above the line on: profit before tax, gross; profit before tax, net; net assets, gross; net assets, net.',
  )
  expect(soft).toHaveTextContent('It reaches the line without the projected misstatements too.')
  expect(soft).toHaveTextContent('Required')
  expect(soft).toHaveTextContent('no partner acknowledgement is recorded')

  expect(panel('Sign-off')).toHaveTextContent('Blocked')
  expect(softGate.sign_off_gate.blocked_by).toHaveLength(1)
  expect(
    within(panel('Sign-off')).getByText(softGate.sign_off_gate.blocked_by[0] ?? 'missing'),
  ).toBeInTheDocument()
  // The size of the misstatements alone does not block the opinion here.
  expect(panel('Opinion gate')).toHaveTextContent('Open')
  expect(panel('Hard gate: overall materiality')).toHaveTextContent('Clear')
})

test('the hard gate firing blocks the opinion, and says when it depends on projected items', async () => {
  await open(hardGate)
  const hard = panel('Hard gate: overall materiality')
  expect(hard).toHaveTextContent('Fires')
  expect(hardGate.evaluation.gates.hard.depends_on_projected).toBe(true)
  expect(hard).toHaveTextContent(
    'It reaches the line only with the projected misstatements counted.',
  )
  expect(hard).not.toHaveTextContent('without the projected misstatements too')

  const opinion = panel('Opinion gate')
  expect(opinion).toHaveTextContent('Blocked')
  expect(
    within(opinion).getByText(hardGate.opinion_gate.blocked_by[0] ?? 'missing'),
  ).toBeInTheDocument()
  expect(hardGate.opinion_gate.blocked_by[0]).toContain('pending decision B8')

  const signOff = within(panel('Sign-off'))
  expect(hardGate.sign_off_gate.blocked_by).toHaveLength(2)
  for (const reason of hardGate.sign_off_gate.blocked_by) {
    expect(signOff.getByText(reason)).toBeInTheDocument()
  }
})

test('an item above PM not yet dealt with is named and blocks sign-off', async () => {
  await open(itemAbovePm)
  const items = panel('Individual items')
  expect(items).toHaveTextContent('Present')
  expect(items).toHaveTextContent('Individually significant (above PM): M-1.')
  expect(items).toHaveTextContent(
    'Blocking sign-off until corrected, refused with a reason or withdrawn: M-1.',
  )
  expect(
    within(panel('Sign-off')).getByText('M-1 is individually significant and raised'),
  ).toBeInTheDocument()
  expect(within(items).getByText(itemAbovePm.evaluation.tests.individual.basis)).toBeInTheDocument()
})

test('an evaluation that cannot be completed is undetermined, and says why', async () => {
  await open(spineDown)
  expect(panel('Hard gate: overall materiality')).toHaveTextContent('Indeterminate')
  expect(panel('Soft gate: performance materiality')).toHaveTextContent('Indeterminate')
  const opinion = panel('Opinion gate')
  expect(opinion).toHaveTextContent('Undetermined')
  expect(opinion).toHaveTextContent('Undetermined because')
  for (const reason of spineDown.opinion_gate.undetermined_because) {
    expect(within(opinion).getByText(reason)).toBeInTheDocument()
  }
  expect(spineDown.opinion_gate.undetermined_because).toContain(
    'an uncorrected item could not be aggregated against overall materiality',
  )
  const signOff = panel('Sign-off')
  expect(signOff).toHaveTextContent('Undetermined')
  for (const reason of spineDown.sign_off_gate.undetermined_because) {
    expect(within(signOff).getByText(reason)).toBeInTheDocument()
  }
  expect(panel('Individual items')).toHaveTextContent('Cannot be banded: M-1, M-2, M-4, M-6.')
})

test('with no thresholds no gate can be evaluated, and the backend’s reason is shown', async () => {
  await open(empty)
  expect(panel('Hard gate: overall materiality')).toHaveTextContent('No thresholds')
  expect(panel('Hard gate: overall materiality')).toHaveTextContent('Not set')
  expect(panel('Soft gate: performance materiality')).toHaveTextContent('No thresholds')
  expect(panel('Opinion gate')).toHaveTextContent('Undetermined')
  expect(within(panel('Opinion gate')).getByText('no thresholds have been set')).toBeInTheDocument()
  expect(within(panel('Sign-off')).getByText('no thresholds have been set')).toBeInTheDocument()
})

// ---- partner-only actions ----

test('without a trusted role claim the acknowledgement is shown as unavailable, with the reason', async () => {
  await open(softGate)
  const partner = softGate.evaluation.authorisation.partner_actions
  expect(partner.available).toBe(false)
  const soft = panel('Soft gate: performance materiality')
  expect(soft).toHaveTextContent('Acknowledge the soft gate')
  expect(within(soft).getByText('Unavailable')).toBeInTheDocument()
  expect(within(soft).getByText(partner.detail)).toBeInTheDocument()
})

test('an acknowledgement is not mentioned when the backend does not ask for one', async () => {
  await open(clearNoRun)
  expect(screen.queryByText('Acknowledge the soft gate')).not.toBeInTheDocument()
})

test('without a trusted role claim no partner-only action can be sent from this screen', async () => {
  // In development mode the backend reports that no partner can be named. Neither form is
  // offered, however the gates stand. (Where one can be named: partnerForms.test.tsx.)
  for (const snapshot of [softGate, hardGate, clearNoRun, itemAbovePm]) {
    const view = await open(snapshot)
    expect(snapshot.evaluation.authorisation.partner_actions.available).toBe(false)
    expect(screen.queryByRole('button', { name: /acknowledge|conclu|material/i })).toBeNull()
    // The only inputs are the two this screen may send: the run and the strategy answer.
    expect(screen.getAllByRole('checkbox')).toHaveLength(1)
    expect(screen.queryAllByRole('textbox')).toEqual([])
    view.unmount()
  }
})

// ---- evaluation history ----

test('with no run recorded the history says so', async () => {
  await open(clearNoRun)
  const history = panel('Evaluation runs')
  expect(history).toHaveTextContent('Latest run:None recordedno evaluation run has been recorded')
  expect(history).toHaveTextContent('No evaluation run has been recorded yet.')
  expect(screen.queryByRole('table', { name: 'Evaluation runs, newest first' })).toBeNull()
})

test('a run shows its figures, the threshold version, who recorded it and when', async () => {
  await open(runCurrent)
  const run = runCurrent.runs[0]
  if (run === undefined) throw new Error('the fixture has no run')
  const cellsOfRun = within(runRow(1))
    .getAllByRole('cell')
    .map((cell) => cell.textContent)
  expect(cellsOfRun.slice(0, 7)).toEqual([
    `${dateTime(run.at)}by manager@firm`,
    'Version 1',
    '₹1,95,000.00',
    '-₹1,95,000.00',
    '₹1,95,000.00',
    '-₹1,95,000.00',
    'Current',
  ])
  expect([run.agg_gross_pbt, run.agg_net_pbt, run.agg_gross_na, run.agg_net_na]).toEqual([
    '195000.00',
    '-195000.00',
    '195000.00',
    '-195000.00',
  ])
  expect(panel('Evaluation runs')).toHaveTextContent(
    'Latest run:Currentthe latest run describes the evaluation as it stands',
  )
})

test('a run the evaluation has moved on from is stale, for the backend’s reason', async () => {
  await open(runStale)
  expect(panel('Evaluation runs')).toHaveTextContent(
    'Latest run:Stalea misstatement has been raised, moved or re-banded since the latest run was recorded',
  )
  expect(within(runRow(1)).getByText('Stale')).toBeInTheDocument()
  // The run still shows the figures it was recorded with, not today's.
  expect(within(runRow(1)).getAllByText('₹1,95,000.00')).toHaveLength(2)
  expect(cells(aggregate(), /^Profit before tax gross/)[0]).toBe('₹2,10,000.00')
})

test('a run recorded without its lists says only whether each item was uncorrected', async () => {
  // A run from before the lists existed: the screen does not guess what it summed.
  const older: Snapshot = {
    ...twoRuns,
    runs: twoRuns.runs.map((run) => {
      const detail = { ...run.detail }
      delete detail.counted
      delete detail.not_accumulated
      return { ...run, detail }
    }),
  }
  await open(older)
  fireEvent.click(within(runRow(1)).getByRole('button', { name: 'Inspect run 1' }))
  const items = screen.getByRole('table', { name: 'Misstatements as they stood in run 1' })
  expect(
    within(within(items).getByRole('row', { name: /^M-2/ }))
      .getAllByRole('cell')
      .map((cell) => cell.textContent),
  ).toEqual(['Factual', 'Raised', 'Clearly trivial', 'Yes'])
  expect(panel('Evaluation runs')).not.toHaveTextContent('Clearly trivial, not accumulated')
})

test('every run is listed, newest first, and only the latest can be current', async () => {
  await open(twoRuns)
  const rows = within(runs())
    .getAllByRole('rowheader')
    .map((header) => header.textContent)
  expect(rows).toEqual(['Run 2Run', 'Run 1Run'])
  expect(within(runRow(2)).getByText('Current')).toBeInTheDocument()
  expect(within(runRow(2)).getAllByText('₹2,10,000.00')).toHaveLength(2)
  expect(within(runRow(1)).getByText('Earlier')).toBeInTheDocument()
  expect(within(runRow(1)).getAllByText('₹1,95,000.00')).toHaveLength(2)
})

test('a run can be inspected: what it recorded, exactly as it was written', async () => {
  await open(twoRuns)
  const inspect = within(runRow(1)).getByRole('button', { name: 'Inspect run 1' })
  expect(inspect).toHaveAttribute('aria-expanded', 'false')
  expect(screen.queryByRole('table', { name: /as they stood in run 1/ })).toBeNull()

  fireEvent.click(inspect)
  expect(within(runRow(1)).getByRole('button', { name: 'Close run 1' })).toHaveAttribute(
    'aria-expanded',
    'true',
  )
  const items = screen.getByRole('table', { name: 'Misstatements as they stood in run 1' })
  const first = twoRuns.runs.find((run) => run.run_no === 1)
  expect(
    within(items)
      .getAllByRole('rowheader')
      .map((header) => header.textContent),
  ).toEqual(first?.detail.items?.map((item) => item.ref))
  expect(
    within(within(items).getByRole('row', { name: /^M-3/ }))
      .getAllByRole('cell')
      .map((cell) => cell.textContent),
  ).toEqual(['Judgemental', 'Refused', 'Accumulated', 'Yes'])
  expect(
    within(within(items).getByRole('row', { name: /^M-5/ }))
      .getAllByRole('cell')
      .map((cell) => cell.textContent),
  ).toEqual(['Factual', 'Corrected', 'Individually significant', 'No'])
  // A clearly trivial item is uncorrected and still not counted: the run says which it is.
  expect(
    within(within(items).getByRole('row', { name: /^M-2/ }))
      .getAllByRole('cell')
      .map((cell) => cell.textContent),
  ).toEqual(['Factual', 'Raised', 'Clearly trivial', 'No: clearly trivial'])
  // Run 1 was made before M-7 was raised, and still says so.
  expect(within(items).queryByRole('row', { name: /^M-7/ })).toBeNull()

  const detail = panel('Evaluation runs')
  expect(detail).toHaveTextContent('Version 1: CTT ₹12,500.00 · PM ₹2,50,000.00 · OM ₹4,00,000.00')
  expect(detail).toHaveTextContent('₹1,50,000.00 gross, -₹1,50,000.00 net')
  expect(detail).toHaveTextContent('Materiality reassessedYes')
  // What the run left out for being clearly trivial is kept with it.
  expect(first?.detail.not_accumulated).toEqual(['M-2'])
  expect(detail).toHaveTextContent('Clearly trivial, not accumulatedM-2')
  expect(detail).toHaveTextContent('Hard gate thenClear')
  expect(detail).toHaveTextContent('Sign-off thenNot blocked')

  // Inspecting another run closes this one; closing shows none.
  fireEvent.click(within(runRow(2)).getByRole('button', { name: 'Inspect run 2' }))
  expect(screen.queryByRole('table', { name: 'Misstatements as they stood in run 1' })).toBeNull()
  expect(
    screen.getByRole('table', { name: 'Misstatements as they stood in run 2' }),
  ).toBeInTheDocument()
  fireEvent.click(within(runRow(2)).getByRole('button', { name: 'Close run 2' }))
  expect(screen.queryByRole('table', { name: /as they stood in run/ })).toBeNull()
})

// ---- the strategy prompt ----

test('with no band declared the strategy trigger is not evaluated, and the backend says why', async () => {
  await open(clearNoRun)
  const strategy = panel('Audit strategy prompt')
  expect(strategy).toHaveTextContent('Not configured')
  expect(
    within(strategy).getByText(clearNoRun.evaluation.gates.strategy_trigger.detail),
  ).toBeInTheDocument()
  expect(clearNoRun.evaluation.gates.strategy_trigger.detail).toContain('pending decision B5')
  expect(screen.queryByRole('form', { name: 'Answer the strategy prompt' })).toBeNull()
})

test('when the trigger fires the line, the measures and the need for an answer are shown', async () => {
  await open(strategyRequired)
  const strategy = panel('Audit strategy prompt')
  expect(strategy).toHaveTextContent('Fires')
  expect(strategy).toHaveTextContent(
    'Line: ₹2,00,000.00, the declared fraction 0.5 of overall materiality. At or above it on: profit before tax, gross; profit before tax, net; net assets, gross; net assets, net.',
  )
  expect(strategy).toHaveTextContent('Answer:Requiredthe strategy prompt has not been answered')
  expect(screen.getByRole('form', { name: 'Answer the strategy prompt' })).toBeInTheDocument()
  // The prompt blocks nothing: the gates are as they were.
  expect(panel('Sign-off')).toHaveTextContent('Open')
})

test('once answered on the current figures the prompt asks nothing more', async () => {
  await open(strategyRecorded)
  const strategy = panel('Audit strategy prompt')
  expect(strategy).toHaveTextContent('Answer:Recordedanswered on these figures')
  expect(screen.queryByRole('form', { name: 'Answer the strategy prompt' })).toBeNull()
})

// ---- conclusion ----

test('with no conclusion the page says so and shows whether one could be recorded', async () => {
  await open(clearNoRun)
  const conclusion = panel('Conclusion')
  expect(conclusion).toHaveTextContent(
    'Latest conclusion:None recordedno conclusion has been recorded',
  )
  expect(conclusion).toHaveTextContent('That the misstatements are not material:Not blocked')
  expect(conclusion).toHaveTextContent('That the misstatements are material:Not blocked')
  expect(conclusion).toHaveTextContent(
    `A conclusion also requires: ${clearNoRun.evaluation.conclusion.requires}.`,
  )
  expect(conclusion).toHaveTextContent('No conclusion has been recorded.')
})

test('a gate that fires blocks the conclusion of not material, for the backend’s reasons', async () => {
  await open(softGate)
  const conclusion = panel('Conclusion')
  expect(conclusion).toHaveTextContent('That the misstatements are not material:Blocked')
  for (const reason of softGate.evaluation.conclusion.allowed.not_material.reasons) {
    expect(within(conclusion).getByText(reason)).toBeInTheDocument()
  }
  expect(softGate.evaluation.conclusion.allowed.not_material.reasons).toHaveLength(1)
  // A gate that fires is the subject of the other conclusion, not a bar to it.
  expect(conclusion).toHaveTextContent('That the misstatements are material:Not blocked')
})

test('an unfinished evaluation blocks both conclusions', async () => {
  await open(itemAbovePm)
  const conclusion = panel('Conclusion')
  expect(conclusion).toHaveTextContent('That the misstatements are not material:Blocked')
  expect(conclusion).toHaveTextContent('That the misstatements are material:Blocked')
  expect(itemAbovePm.evaluation.conclusion.allowed.material.reasons).toEqual([
    'M-1 is individually significant and raised',
  ])
})

test('recording a conclusion is shown as unavailable when no partner can be named', async () => {
  await open(clearNoRun)
  const conclusion = panel('Conclusion')
  const partner = clearNoRun.evaluation.authorisation.partner_actions
  expect(conclusion).toHaveTextContent('Record a conclusion')
  expect(within(conclusion).getByText('Unavailable')).toBeInTheDocument()
  expect(within(conclusion).getByText(partner.detail)).toBeInTheDocument()
  expect(partner.detail).toContain('fails closed')
})

test('where a partner can be named it is shown as reserved to the partner, and its form is offered', async () => {
  await open(partnerAvailable)
  const conclusion = panel('Conclusion')
  const partner = partnerAvailable.evaluation.authorisation.partner_actions
  expect(partner.available).toBe(true)
  expect(within(conclusion).getByText('Partner only')).toBeInTheDocument()
  expect(within(conclusion).queryByText('Unavailable')).not.toBeInTheDocument()
  expect(within(conclusion).getByText(partner.detail)).toBeInTheDocument()
  // The form is there; whether the person sending it is the partner is the backend's to say.
  expect(within(conclusion).getByRole('form', { name: 'Record a conclusion' })).toBeInTheDocument()
})

test('a recorded conclusion is shown with its words, basis, figures and who concluded', async () => {
  await open(concluded)
  const conclusion = panel('Conclusion')
  const row = concluded.evaluation.conclusion.run
  if (row === null) throw new Error('the fixture has no conclusion')
  expect(conclusion).toHaveTextContent(
    'Latest conclusion:Currentthe latest conclusion stands on the evaluation as it is',
  )
  expect(conclusion).toHaveTextContent('DeterminationNot material')
  expect(conclusion).toHaveTextContent('Concluded bypartner@firm')
  expect(conclusion).toHaveTextContent('RowRun 2, on review of run 1')
  expect(conclusion).toHaveTextContent(
    'ConclusionUncorrected misstatements are not material, individually or in aggregate.',
  )
  expect(conclusion).toHaveTextContent(
    'BasisThe aggregate is below performance materiality on every measure; see C-4.',
  )
  expect(conclusion).toHaveTextContent('Profit before tax₹60,000.00 gross, -₹60,000.00 net')
  expect(conclusion).toHaveTextContent('Net assets₹60,000.00 gross, -₹60,000.00 net')
  expect(conclusion).toHaveTextContent('ThresholdsVersion 1')
  expect(conclusion).toHaveTextContent(dateTime(row.at))
  expect(conclusion).toHaveTextContent('There is no earlier conclusion.')
  // In the history the conclusion is a row of its own, beside the run it reviewed.
  expect(
    within(runs())
      .getAllByRole('rowheader')
      .map((header) => header.textContent),
  ).toEqual(['Run 2Conclusion: Not material', 'Run 1Run'])
})

test('a conclusion the evaluation has moved on from is stale, for the backend’s reason', async () => {
  await open(conclusionStale)
  expect(panel('Conclusion')).toHaveTextContent(
    'Latest conclusion:Stalethe latest conclusion is out of date: a misstatement has been raised, moved or re-banded since it was recorded',
  )
  // It still shows the figures it was saved with.
  expect(panel('Conclusion')).toHaveTextContent('Profit before tax₹60,000.00 gross')
  expect(cells(aggregate(), /^Profit before tax gross/)[0]).toBe('₹78,000.00')
})

test('earlier conclusions are kept and listed, none ever changed', async () => {
  await open(twoConclusions)
  const conclusion = panel('Conclusion')
  expect(twoConclusions.conclusions.map((entry) => entry.run_no)).toEqual([4, 2])
  expect(conclusion).toHaveTextContent('RowRun 4, on review of run 3')
  const earlier = within(
    within(conclusion).getByRole('list', { name: 'Earlier conclusions' }),
  ).getAllByRole('listitem')
  expect(earlier).toHaveLength(1)
  expect(earlier[0]).toHaveTextContent('RowRun 2, on review of run 1')
  expect(earlier[0]).toHaveTextContent('Profit before tax₹60,000.00 gross, -₹60,000.00 net')
  expect(
    within(runs())
      .getAllByRole('rowheader')
      .map((header) => header.textContent),
  ).toEqual([
    'Run 4Conclusion: Not material',
    'Run 3Run',
    'Run 2Conclusion: Not material',
    'Run 1Run',
  ])
})

test('opening another engagement loads that one', async () => {
  mockApi({ ...evaluationAnswers(clearNoRun), ...evaluationAnswers(softGate) })
  const view = render(<EvaluationPage id={clearNoRun.engagement.id} />)
  await screen.findByRole('heading', { level: 1, name: clearNoRun.engagement.label })
  view.rerender(<EvaluationPage id={softGate.engagement.id} />)
  expect(
    await screen.findByRole('heading', { level: 1, name: softGate.engagement.label }),
  ).toBeInTheDocument()
  expect(panel('Soft gate: performance materiality')).toHaveTextContent('Fires')
})

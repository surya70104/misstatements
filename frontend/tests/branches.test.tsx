// The eight display branches the register listed as coded and untested (V11). Each is now
// reached by a real answer of the backend, captured by
// backend/tests/test_frontend_fixtures.py with the Financial Spine double moved into the
// situation the branch is for. Nothing here is hand-written data.
import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import type { Misstatement } from '../src/api'
import { EvaluationPage } from '../src/pages/EvaluationPage'
import { MisstatementPage } from '../src/pages/MisstatementPage'
import { SchedulePage } from '../src/pages/SchedulePage'
import { branch, refuse } from './closureFixtures'
import { evaluationAnswers, type Snapshot } from './evaluationFixtures'
import { answered, mockApi } from './mockApi'
import { scheduleAnswers } from './scheduleFixtures'

afterEach(() => {
  vi.unstubAllGlobals()
})

async function openDetail(misstatement: Misstatement, answers: Record<string, unknown> = {}) {
  mockApi({ [`GET /api/misstatements/${misstatement.id}`]: misstatement, ...answers })
  render(<MisstatementPage id={misstatement.id} />)
  await screen.findByRole('heading', { level: 1 })
}

async function openEvaluation(snapshot: Snapshot) {
  mockApi(evaluationAnswers(snapshot))
  render(<EvaluationPage id={snapshot.engagement.id} />)
  await screen.findByRole('region', { name: 'Gates and sign-off' })
}

async function openSchedule(snapshot: Snapshot, misstatements: Misstatement[]) {
  const id = snapshot.engagement.id
  mockApi(
    scheduleAnswers(id, {
      engagement: snapshot.engagement,
      misstatements,
      evaluation: snapshot.evaluation,
    }),
  )
  render(<SchedulePage id={id} />)
  await screen.findByRole('table', { name: 'Schedule of misstatements' })
}

function panel(name: string): HTMLElement {
  return screen.getByRole('region', { name })
}

// ---- 1. a judgemental range that crosses performance materiality ----

test('branch 1: a judgemental range that crosses PM is flagged on the detail', async () => {
  expect(branch.rangeCrossesPm.banding.range_crosses_pm).toBe(true)
  expect(branch.rangeCrossesPm.band).toBe('accumulated')
  await openDetail(branch.rangeCrossesPm)
  const identification = panel('Identification')
  expect(identification).toHaveTextContent('₹2,00,000.00 to ₹3,00,000.00')
  expect(within(identification).getByText('Range crosses PM')).toBeInTheDocument()
  // The band itself is still computed on the point estimate, which is below PM.
  expect(within(identification).getByText('Accumulated')).toBeInTheDocument()
})

test('branch 1: the schedule says so beside the band', async () => {
  // The same misstatement as the schedule lists it, refused by then.
  const listed = branch.stateDiffersSchedule.find((entry) => entry.id === branch.rangeCrossesPm.id)
  expect(listed?.banding.range_crosses_pm).toBe(true)
  await openSchedule(branch.stateDiffersEvaluation, branch.stateDiffersSchedule)
  const row = screen.getByRole('row', { name: new RegExp(`^${branch.rangeCrossesPm.ref} `) })
  expect(within(row).getByText('Range crosses PM')).toBeInTheDocument()
})

// ---- 2. a state that differs from the Financial Spine's ----

test('branch 2: a state the Spine disagrees with is flagged on the detail, in the backend’s words', async () => {
  const consistency = branch.stateDiffers.state_consistency
  expect(consistency.consistent).toBe(false)
  await openDetail(branch.stateDiffers)
  const alert = within(panel('State history')).getByRole('alert')
  expect(alert).toHaveTextContent('This state differs from the Financial Spine.')
  expect(alert).toHaveTextContent(consistency.detail ?? 'missing')
  expect(consistency.detail).toContain('the Spine holds it accepted')
  expect(panel('Dr/Cr lines')).toHaveTextContent('Statusaccepted')
})

test('branch 2: the schedule flags the same item, and the evaluation names it', async () => {
  await openSchedule(branch.stateDiffersEvaluation, branch.stateDiffersSchedule)
  const row = screen.getByRole('row', { name: new RegExp(`^${branch.stateDiffers.ref} `) })
  expect(row).toHaveTextContent('Differs from the Financial Spine')
  expect(row).toHaveTextContent(branch.stateDiffers.state_consistency.detail ?? 'missing')
})

test('branch 2: the evaluation is undetermined while the two modules disagree', async () => {
  const evaluation = branch.stateDiffersEvaluation.evaluation
  expect(evaluation.state_consistency.inconsistent).toEqual([branch.stateDiffers.ref])
  await openEvaluation(branch.stateDiffersEvaluation)
  expect(panel('Individual items')).toHaveTextContent(
    `State differs from the Financial Spine: ${branch.stateDiffers.ref}.`,
  )
  // The opinion cannot be determined while they disagree, and the backend says why.
  const opinion = panel('Opinion gate')
  expect(branch.stateDiffersEvaluation.opinion_gate.status).toBe('undetermined')
  expect(within(opinion).getByText('Undetermined', { exact: true })).toBeInTheDocument()
  expect(
    within(opinion).getByText('M-2 is communicated here but accepted in the Financial Spine'),
  ).toBeInTheDocument()
  // Sign-off is blocked outright by the soft gate, and the disagreement is listed with it.
  const signOff = panel('Sign-off')
  expect(within(signOff).getByText('Blocked', { exact: true })).toBeInTheDocument()
  expect(branch.stateDiffersEvaluation.sign_off_gate.undetermined_because).toHaveLength(1)
  for (const reason of branch.stateDiffersEvaluation.sign_off_gate.undetermined_because) {
    expect(within(signOff).getByText(reason)).toBeInTheDocument()
  }
})

test('branch 2: a run is refused while they disagree, for the backend’s reason', async () => {
  const snapshot = branch.stateDiffersEvaluation
  mockApi({
    ...evaluationAnswers(snapshot),
    [`POST /api/engagements/${snapshot.engagement.id}/evaluation/runs`]: refuse(
      branch.stateDiffersRunRefused,
    ),
  })
  render(<EvaluationPage id={snapshot.engagement.id} />)
  const form = await screen.findByRole('form', { name: 'Record an evaluation run' })
  fireEvent.click(within(form).getByRole('checkbox'))
  fireEvent.click(within(form).getByRole('button', { name: 'Record evaluation run' }))
  const alert = await within(form).findByRole('alert')
  expect(alert).toHaveTextContent(
    'M-2 disagree with the Financial Spine about their state, so the aggregate would count an item the Spine has posted or leave one out',
  )
  expect(alert).toHaveTextContent('answered 409')
})

// ---- 3 and 4. a ledger not matched in the Spine; an effect unresolved while it is readable ----

test('branch 3: a ledger the Spine no longer matches is named on the detail', async () => {
  expect(branch.unmatched.classification?.unmatched).toEqual(['Salaries', 'Salaries'])
  expect(branch.unmatched.spine.status).toBe('ok')
  await openDetail(branch.unmatched)
  expect(panel('Financial effects')).toHaveTextContent(
    'Not matched to a ledger in the Financial Spine now: Salaries, Salaries.',
  )
  expect(
    screen.queryByText('The Financial Spine classifies every line the same way now.'),
  ).not.toBeInTheDocument()
})

test('branch 4: an effect that cannot be determined is disclosed, never shown as nil', async () => {
  expect(branch.unmatched.effects?.profit_before_tax).toBeNull()
  expect(branch.unmatched.effects?.net_assets).toBeNull()
  await openDetail(branch.unmatched)
  const effects = within(panel('Financial effects'))
  const pbt = effects.getByRole('heading', { name: 'Effect on profit before tax' }).parentElement
  const na = effects.getByRole('heading', { name: 'Effect on net assets' }).parentElement
  for (const effect of [pbt, na]) {
    expect(effect).toHaveTextContent('Not available')
    expect(effect).toHaveTextContent('These ledgers cannot be classified: Salaries, Salaries.')
    expect(effect).not.toHaveTextContent('₹')
  }
  // The backend's own explanation is shown beside it, and there is no band.
  expect(pbt).toHaveTextContent(branch.unmatched.effects?.profit_basis ?? 'missing')
  expect(branch.unmatched.band).toBeNull()
  expect(panel('Financial effects')).toHaveTextContent('Not banded')
  expect(panel('Financial effects')).toHaveTextContent(branch.unmatched.band_basis ?? 'missing')
  // The Spine itself is readable: the lines are still shown.
  expect(screen.getByRole('table', { name: /Dr\/Cr lines/ })).toBeInTheDocument()
})

test('branch 4: the schedule shows the reason in place of the two effects', async () => {
  await openSchedule(branch.unmatchedEvaluation, branch.unmatchedSchedule)
  const row = screen.getByRole('row', { name: new RegExp(`^${branch.unmatched.ref} `) })
  const cells = within(row).getAllByRole('cell')
  expect(cells[3]).toHaveTextContent('Not availableCannot be classified: Salaries, Salaries')
  expect(cells[4]).toHaveTextContent('Not availableCannot be classified: Salaries, Salaries')
  expect(cells[5]).toHaveTextContent('Not banded')
  // The lines are the Spine's and are still there.
  expect(cells[2]).toHaveTextContent('₹20,000.00')
  expect(
    screen.getByText(/These totals are incomplete: 1 misstatement could not be aggregated/),
  ).toBeInTheDocument()
})

// ---- 5. a move the Spine had already decided ----

test('branch 5: a move the Spine had already decided is recorded, and says nothing was decided twice', async () => {
  expect(branch.alreadyDecided.transition).toEqual({
    spine_decision: 'accepted',
    decided_now: false,
    note: null,
    adjustment_status: 'accepted',
  })
  const id = branch.stateDiffers.id
  await openDetail(branch.stateDiffers, {
    [`POST /api/misstatements/${id}/transitions`]: answered(201, branch.alreadyDecided),
  })
  const actions = panel('Workflow actions')
  fireEvent.click(within(actions).getByRole('button', { name: 'Record correction' }))
  fireEvent.click(within(actions).getByRole('button', { name: 'Confirm: corrected' }))
  expect(
    await screen.findByText(`Recorded: ${branch.stateDiffers.ref} is now corrected.`),
  ).toBeInTheDocument()
  expect(actions).toHaveTextContent(
    'Financial Spine: adjustment accepted (it had already been decided this way).',
  )
  // The two modules agree again, so the warning is gone.
  expect(branch.alreadyDecided.state_consistency.consistent).toBe(true)
  expect(within(panel('State history')).queryByRole('alert')).not.toBeInTheDocument()
})

// ---- 6. a stale acknowledgement ----

test('branch 6: an acknowledgement the figures have moved on from is stale, and asked for again', async () => {
  const soft = branch.acknowledgementStale.evaluation.gates.soft
  expect(soft.acknowledgement.status).toBe('stale')
  await openEvaluation(branch.acknowledgementStale)
  const gate = panel('Soft gate: performance materiality')
  expect(gate).toHaveTextContent('Partner acknowledgement:Stale')
  expect(gate).toHaveTextContent('the aggregate has changed since the last acknowledgement')
  // It is asked for again, and where a partner can be named the form is offered again.
  expect(within(gate).getByRole('form', { name: 'Acknowledge the soft gate' })).toBeInTheDocument()
  expect(panel('Sign-off')).toHaveTextContent('Blocked')
})

// ---- 7. a stale strategy answer ----

test('branch 7: a strategy answer the figures have moved on from is stale, and asked for again', async () => {
  const trigger = branch.strategyStale.evaluation.gates.strategy_trigger
  expect(trigger.response).toEqual({
    status: 'stale',
    detail: 'the aggregate has changed since the last answer',
  })
  await openEvaluation(branch.strategyStale)
  const strategy = panel('Audit strategy prompt')
  expect(strategy).toHaveTextContent('Answer:Stalethe aggregate has changed since the last answer')
  expect(
    within(strategy).getByRole('form', { name: 'Answer the strategy prompt' }),
  ).toBeInTheDocument()
})

// ---- 8. an item at or above overall materiality on its own ----

test('branch 8: an item at or above OM on its own is named among the individual items', async () => {
  const individual = branch.itemAtOm.evaluation.tests.individual
  expect(individual.at_or_above_om).toEqual(['M-1'])
  await openEvaluation(branch.itemAtOm)
  const items = panel('Individual items')
  expect(items).toHaveTextContent('Present')
  expect(items).toHaveTextContent('At or above overall materiality on their own: M-1.')
  expect(items).toHaveTextContent('Individually significant (above PM): M-1.')
  // One item is also the whole aggregate: the hard gate fires on it.
  expect(panel('Hard gate: overall materiality')).toHaveTextContent('Fires')
  expect(panel('Opinion gate')).toHaveTextContent('Blocked')
})

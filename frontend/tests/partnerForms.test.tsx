// The two writes reserved to the engagement partner (register S3): the acknowledgement of
// the soft gate and the conclusion. The fixtures were captured from the backend run the way
// production runs it, with header identity behind a trusted proxy and the partner named by
// the proxy's role claim (backend/tests/test_frontend_fixtures.py). The screens name no
// partner: they send the form, and the backend accepts it or refuses it.
import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { EvaluationPage } from '../src/pages/EvaluationPage'
import {
  acknowledged,
  acknowledgementRecorded,
  acknowledgementRequired,
  conclusionMaterialRecorded,
  conclusionRecorded,
  partnerConcluded,
  partnerConcludedMaterial,
  partnerRefusals,
  refuse,
} from './closureFixtures'
import {
  clearNoRun,
  evaluationAnswers,
  evaluationAnswersInTurn,
  hardGate,
  partnerAvailable,
  refusals,
  runStale,
  softGate,
  type Snapshot,
} from './evaluationFixtures'
import { answered, deferred, inTurn, mockApi, requested, sent } from './mockApi'

afterEach(() => {
  vi.unstubAllGlobals()
})

async function open(snapshot: Snapshot, answers: Record<string, unknown> = {}) {
  mockApi({ ...evaluationAnswers(snapshot), ...answers })
  const view = render(<EvaluationPage id={snapshot.engagement.id} />)
  await screen.findByRole('heading', { level: 1 })
  return view
}

function panel(name: string): HTMLElement {
  return screen.getByRole('region', { name })
}

function acknowledgementPath(snapshot: Snapshot): string {
  return `POST /api/engagements/${snapshot.engagement.id}/evaluation/soft-gate-acknowledgements`
}

function conclusionPath(snapshot: Snapshot, kind: 'not-material' | 'material'): string {
  return `POST /api/engagements/${snapshot.engagement.id}/evaluation/conclusions/${kind}`
}

function posts(): string[] {
  return requested().filter((request) => request.startsWith('POST'))
}

const WORDS = 'Uncorrected misstatements are not material, individually or in aggregate.'
const BASIS = 'The aggregate is at performance materiality and below overall materiality; C-4.'

function conclusionForm(): HTMLElement {
  return screen.getByRole('form', { name: 'Record a conclusion' })
}

function fillConclusion(kind: RegExp) {
  const form = conclusionForm()
  fireEvent.click(within(form).getByRole('radio', { name: kind }))
  fireEvent.change(within(form).getByLabelText(/^Conclusion, in the partner’s words/), {
    target: { value: WORDS },
  })
  fireEvent.change(within(form).getByLabelText(/^Basis/), { target: { value: BASIS } })
  fireEvent.click(within(form).getByRole('checkbox', { name: /Materiality was reassessed/ }))
}

const NOT_MATERIAL = /are not material/
const MATERIAL = /misstatements are material$/

// =====================================================================================
// Where no partner can be named, nothing is offered
// =====================================================================================

test('without a trusted role claim neither partner form is offered, and the backend’s reason is shown', async () => {
  for (const snapshot of [softGate, hardGate, clearNoRun]) {
    const view = await open(snapshot)
    const partner = snapshot.evaluation.authorisation.partner_actions
    expect(partner.available).toBe(false)
    expect(screen.queryByRole('form', { name: 'Acknowledge the soft gate' })).toBeNull()
    expect(screen.queryByRole('form', { name: 'Record a conclusion' })).toBeNull()
    expect(screen.queryByRole('button', { name: /acknowledge|conclusion/i })).toBeNull()
    const conclusion = panel('Conclusion')
    expect(within(conclusion).getByText('Unavailable')).toBeInTheDocument()
    expect(within(conclusion).getByText(partner.detail)).toBeInTheDocument()
    view.unmount()
  }
})

// =====================================================================================
// The acknowledgement of the soft gate
// =====================================================================================

test('where a partner can be named and the gate asks, the acknowledgement is offered', async () => {
  await open(acknowledgementRequired)
  const evaluation = acknowledgementRequired.evaluation
  expect(evaluation.authorisation.partner_actions.available).toBe(true)
  expect(evaluation.gates.soft.acknowledgement.status).toBe('required')
  const gate = panel('Soft gate: performance materiality')
  expect(within(gate).getByText('Partner only')).toBeInTheDocument()
  expect(within(gate).getByText(evaluation.authorisation.partner_actions.detail)).toBeVisible()
  const form = within(gate).getByRole('form', { name: 'Acknowledge the soft gate' })
  // A note is offered and is not required: the spec asks for the acknowledgement.
  expect(within(form).getByLabelText(/^Note/)).not.toBeRequired()
  expect(within(form).getByRole('button', { name: 'Acknowledge the soft gate' })).toBeEnabled()
})

test('the acknowledgement is not offered when the gate does not ask for one', async () => {
  await open(partnerAvailable)
  expect(partnerAvailable.evaluation.gates.soft.acknowledgement.status).toBe('not_required')
  expect(screen.queryByRole('form', { name: 'Acknowledge the soft gate' })).toBeNull()
})

test('acknowledging sends the note, then reads the evaluation again', async () => {
  await open(acknowledgementRequired, {
    ...evaluationAnswersInTurn(acknowledgementRequired, acknowledged, inTurn),
    [acknowledgementPath(acknowledgementRequired)]: answered(201, acknowledgementRecorded),
  })
  expect(panel('Sign-off')).toHaveTextContent('Blocked')
  const form = screen.getByRole('form', { name: 'Acknowledge the soft gate' })
  fireEvent.change(within(form).getByLabelText(/^Note/), {
    target: { value: '  Reviewed with the manager; see C-4  ' },
  })
  fireEvent.click(within(form).getByRole('button', { name: 'Acknowledge the soft gate' }))
  expect(await screen.findByText('acknowledged on these figures')).toBeInTheDocument()
  expect(sent()).toEqual([
    {
      request: `POST /api/engagements/${acknowledgementRequired.engagement.id}/evaluation/soft-gate-acknowledgements`,
      body: { note: 'Reviewed with the manager; see C-4' },
      contentType: 'application/json',
    },
  ])
  // Once acknowledged the gate asks for nothing more, and sign-off is no longer blocked.
  const gate = panel('Soft gate: performance materiality')
  expect(gate).toHaveTextContent('Partner acknowledgement:Acknowledged')
  expect(screen.queryByRole('form', { name: 'Acknowledge the soft gate' })).toBeNull()
  expect(within(panel('Sign-off')).getByText('Open', { exact: true })).toBeInTheDocument()
  expect(requested().filter((request) => request.startsWith('GET'))).toHaveLength(12)
})

test('an acknowledgement with no note sends none', async () => {
  await open(acknowledgementRequired, {
    [acknowledgementPath(acknowledgementRequired)]: answered(201, acknowledgementRecorded),
  })
  fireEvent.click(screen.getByRole('button', { name: 'Acknowledge the soft gate' }))
  await screen.findByText('Recorded: the acknowledgement of the soft gate.')
  expect(sent().map((entry) => entry.body)).toEqual([{}])
})

test('someone who is not the partner is refused by the backend, in its words', async () => {
  await open(acknowledgementRequired, {
    [acknowledgementPath(acknowledgementRequired)]: refuse(
      partnerRefusals.acknowledgementNotAPartner,
    ),
  })
  fireEvent.click(screen.getByRole('button', { name: 'Acknowledge the soft gate' }))
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent('The acknowledgement was not recorded')
  expect(alert).toHaveTextContent(
    "'senior@firm' does not hold the partner role 'engagement-partner' according to the identity provider; this action is reserved to a partner (spec section 7). Nothing was written (architecture D39).",
  )
  expect(alert).toHaveTextContent('answered 403')
  expect(screen.queryByText(/^Recorded:/)).not.toBeInTheDocument()
  // Nothing was read again, and the gate still asks.
  expect(requested().filter((request) => request.startsWith('GET'))).toHaveLength(6)
  expect(panel('Soft gate: performance materiality')).toHaveTextContent(
    'Partner acknowledgement:Required',
  )
})

test('an acknowledgement already given on these figures is refused, in the backend’s words', async () => {
  await open(acknowledgementRequired, {
    [acknowledgementPath(acknowledgementRequired)]: refuse(partnerRefusals.acknowledgementTwice),
  })
  fireEvent.click(screen.getByRole('button', { name: 'Acknowledge the soft gate' }))
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'these figures are already acknowledged on this threshold version',
  )
})

test('an acknowledgement goes out once while it is processing', async () => {
  const pending = deferred()
  await open(acknowledgementRequired, {
    [acknowledgementPath(acknowledgementRequired)]: pending.answer,
  })
  const form = screen.getByRole('form', { name: 'Acknowledge the soft gate' })
  const button = within(form).getByRole('button', { name: 'Acknowledge the soft gate' })
  fireEvent.click(button)
  fireEvent.click(button)
  fireEvent.submit(form)
  expect(posts()).toHaveLength(1)
  expect(within(form).getByRole('button', { name: 'Recording…' })).toBeDisabled()
  await act(async () => {
    pending.arrive(answered(201, acknowledgementRecorded))
    await pending.answer
  })
  await screen.findByText('Recorded: the acknowledgement of the soft gate.')
  expect(posts()).toHaveLength(1)
})

// =====================================================================================
// The conclusion
// =====================================================================================

test('where a partner can be named the conclusion form is offered, naming the run reviewed', async () => {
  await open(partnerAvailable)
  const conclusion = panel('Conclusion')
  const partner = partnerAvailable.evaluation.authorisation.partner_actions
  expect(partner.available).toBe(true)
  expect(within(conclusion).getByText('Partner only')).toBeInTheDocument()
  expect(within(conclusion).queryByText('Unavailable')).not.toBeInTheDocument()
  expect(within(conclusion).getByText(partner.detail)).toBeInTheDocument()
  const form = conclusionForm()
  expect(form).toHaveTextContent(
    'Run reviewed: run 1, which describes the evaluation as it stands.',
  )
  // Spec section 6.4, "with the figures auto-inserted": the form shows the reviewed run's
  // figures, which are the ones the backend saves with the conclusion.
  const run = partnerAvailable.evaluation.latest_run.run
  expect([run?.agg_gross_pbt, run?.agg_net_pbt, run?.agg_gross_na, run?.agg_net_na]).toEqual([
    '60000.00',
    '-60000.00',
    '60000.00',
    '-60000.00',
  ])
  expect(form).toHaveTextContent(
    'Figures saved with it: profit before tax ₹60,000.00 gross and -₹60,000.00 net; net assets ₹60,000.00 gross and -₹60,000.00 net; thresholds version 1.',
  )
  expect(within(form).getByRole('radio', { name: NOT_MATERIAL })).toBeEnabled()
  expect(within(form).getByRole('radio', { name: MATERIAL })).toBeEnabled()
})

test('a conclusion cannot be sent empty: the kind, the words, the basis and the reassessment are all needed', async () => {
  await open(partnerAvailable)
  const form = conclusionForm()
  const submit = within(form).getByRole('button', { name: 'Record the conclusion' })
  expect(submit).toBeDisabled()
  expect(within(form).getByLabelText(/^Conclusion, in the partner’s words/)).toBeRequired()
  expect(within(form).getByLabelText(/^Basis/)).toBeRequired()

  fireEvent.click(within(form).getByRole('radio', { name: NOT_MATERIAL }))
  fireEvent.change(within(form).getByLabelText(/^Conclusion, in the partner’s words/), {
    target: { value: '   ' },
  })
  fireEvent.change(within(form).getByLabelText(/^Basis/), { target: { value: BASIS } })
  fireEvent.click(within(form).getByRole('checkbox', { name: /Materiality was reassessed/ }))
  expect(submit).toBeDisabled() // spaces are not a conclusion (acceptance 10)
  fireEvent.submit(form)
  expect(posts()).toEqual([])

  fireEvent.change(within(form).getByLabelText(/^Conclusion, in the partner’s words/), {
    target: { value: WORDS },
  })
  expect(submit).toBeEnabled()
  fireEvent.click(within(form).getByRole('checkbox', { name: /Materiality was reassessed/ }))
  expect(submit).toBeDisabled()
})

test('concluding sends the words, the basis and the run reviewed, and never a figure', async () => {
  const snapshot = acknowledged
  const run = snapshot.evaluation.latest_run.run
  if (run === null) throw new Error('the fixture has no run')
  await open(snapshot, {
    ...evaluationAnswersInTurn(snapshot, partnerConcluded, inTurn),
    [conclusionPath(snapshot, 'not-material')]: answered(201, conclusionRecorded),
  })
  fillConclusion(NOT_MATERIAL)
  fireEvent.click(within(conclusionForm()).getByRole('button', { name: 'Record the conclusion' }))
  expect(await screen.findByText(/^Recorded: the conclusion, as run \d+\.$/)).toBeInTheDocument()
  expect(sent()).toEqual([
    {
      request: `POST /api/engagements/${snapshot.engagement.id}/evaluation/conclusions/not-material`,
      body: {
        conclusion: WORDS,
        basis: BASIS,
        reviewed_run_id: run.id,
        materiality_reassessed: true,
      },
      contentType: 'application/json',
    },
  ])
  // The screen was read again: the conclusion is shown with the figures the backend saved.
  const conclusion = panel('Conclusion')
  expect(await within(conclusion).findByText('Not material')).toBeInTheDocument()
  expect(conclusion).toHaveTextContent('Concluded bypartner@firm')
  expect(conclusion).toHaveTextContent('Profit before tax₹2,50,000.00 gross, -₹2,50,000.00 net')
  expect(conclusion).toHaveTextContent(`Conclusion${WORDS}`)
})

test('the other conclusion goes to the other endpoint', async () => {
  const snapshot = acknowledged
  await open(snapshot, {
    [conclusionPath(snapshot, 'material')]: answered(201, conclusionMaterialRecorded),
  })
  fillConclusion(MATERIAL)
  fireEvent.click(within(conclusionForm()).getByRole('button', { name: 'Record the conclusion' }))
  await screen.findByText(/^Recorded: the conclusion, as run \d+\.$/)
  expect(posts()).toEqual([
    `POST /api/engagements/${snapshot.engagement.id}/evaluation/conclusions/material`,
  ])
  expect(partnerConcludedMaterial.evaluation.conclusion.run?.determination).toBe('material')
})

test('a conclusion the backend says its gates would refuse cannot be chosen', async () => {
  await open(acknowledgementRequired)
  const allowed = acknowledgementRequired.evaluation.conclusion.allowed
  expect(allowed.not_material.allowed).toBe(false)
  expect(allowed.material.allowed).toBe(true)
  const form = conclusionForm()
  expect(within(form).getByRole('radio', { name: NOT_MATERIAL })).toBeDisabled()
  expect(within(form).getByRole('radio', { name: MATERIAL })).toBeEnabled()
  expect(form).toHaveTextContent('Blocked by the backend for the reasons given above.')
  for (const reason of allowed.not_material.reasons) {
    expect(within(panel('Conclusion')).getByText(reason)).toBeInTheDocument()
  }
})

test('the gate is in the backend’s write path: a blocked conclusion is refused there, in its words', async () => {
  // The screen still shows the gate as passable, but the figures have moved.
  await open(acknowledged, {
    [conclusionPath(acknowledged, 'not-material')]: refuse(partnerRefusals.conclusionGateBlocked),
  })
  fillConclusion(NOT_MATERIAL)
  fireEvent.click(within(conclusionForm()).getByRole('button', { name: 'Record the conclusion' }))
  const alert = await within(conclusionForm()).findByRole('alert')
  expect(alert).toHaveTextContent('The conclusion was not recorded')
  expect(alert).toHaveTextContent(
    'sign-off is blocked: soft gate: aggregate at or above performance materiality',
  )
  expect(alert).toHaveTextContent('answered 409')
  // Nothing typed is lost, and nothing is claimed.
  expect(within(conclusionForm()).getByLabelText(/^Basis/)).toHaveValue(BASIS)
  expect(screen.queryByText(/^Recorded: the conclusion/)).not.toBeInTheDocument()
})

test('every other refusal of a conclusion is shown in the backend’s words', async () => {
  for (const [captured, words] of [
    [
      refusals.conclusionNotAPartner,
      "'senior@firm' does not hold the partner role 'engagement-partner'",
    ],
    [
      partnerRefusals.conclusionEmpty,
      'conclusion: String should have at least 1 character; basis: String should have at least 1 character',
    ],
    [
      partnerRefusals.conclusionStaleRun,
      'run 1, the one reviewed, no longer describes the evaluation',
    ],
  ] as const) {
    const view = await open(acknowledged, {
      [conclusionPath(acknowledged, 'not-material')]: refuse(captured),
    })
    fillConclusion(NOT_MATERIAL)
    fireEvent.click(within(conclusionForm()).getByRole('button', { name: 'Record the conclusion' }))
    const alert = await within(conclusionForm()).findByRole('alert')
    expect(alert).toHaveTextContent(words)
    expect(alert).toHaveTextContent(`answered ${String(captured.status)}`)
    view.unmount()
    vi.unstubAllGlobals()
  }
})

test('with no current run there is nothing to review, and no conclusion can be sent', async () => {
  // Behind the proxy, but the run no longer describes the evaluation.
  const stale: Snapshot = {
    ...partnerAvailable,
    evaluation: { ...partnerAvailable.evaluation, latest_run: runStale.evaluation.latest_run },
  }
  await open(stale)
  const form = conclusionForm()
  expect(form).toHaveTextContent(
    'A conclusion names the evaluation run that was reviewed, and that run must still describe the evaluation. Record a run first.',
  )
  // No figure is offered as the one to be saved while no run can be reviewed.
  expect(form).not.toHaveTextContent('Figures saved with it')
  fillConclusion(NOT_MATERIAL)
  expect(within(form).getByRole('button', { name: 'Record the conclusion' })).toBeDisabled()
  fireEvent.submit(form)
  expect(posts()).toEqual([])
})

test('a conclusion goes out once while it is processing', async () => {
  const pending = deferred()
  await open(acknowledged, { [conclusionPath(acknowledged, 'not-material')]: pending.answer })
  fillConclusion(NOT_MATERIAL)
  const form = conclusionForm()
  const button = within(form).getByRole('button', { name: 'Record the conclusion' })
  fireEvent.click(button)
  fireEvent.click(button)
  fireEvent.submit(form)
  expect(posts()).toHaveLength(1)
  expect(within(form).getByRole('button', { name: 'Recording…' })).toBeDisabled()
  expect(within(form).getByLabelText(/^Basis/)).toBeDisabled()
  await act(async () => {
    pending.arrive(answered(201, conclusionRecorded))
    await pending.answer
  })
  await screen.findByText(/^Recorded: the conclusion/)
  expect(posts()).toHaveLength(1)
})

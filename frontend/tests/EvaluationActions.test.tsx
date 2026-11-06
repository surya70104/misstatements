// The two writes the evaluation screen sends: recording an evaluation run and answering the
// strategy prompt. Every answer and every refusal below is the backend's real one, captured
// by backend/tests/test_frontend_fixtures.py as the same engagement moved on.
import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { EvaluationPage } from '../src/pages/EvaluationPage'
import {
  clearNoRun,
  empty,
  evaluationAnswers,
  evaluationAnswersInTurn,
  refusals,
  runCurrent,
  runRecorded,
  runsPath,
  spineDown,
  strategyPath,
  strategyRecorded,
  strategyRequired,
  strategyResponse,
  type Snapshot,
} from './evaluationFixtures'
import { answered, deferred, failApi, inTurn, mockApi, refusal, requested, sent } from './mockApi'

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

function runForm(): HTMLElement {
  return screen.getByRole('form', { name: 'Record an evaluation run' })
}

function reassessed(): HTMLElement {
  return within(runForm()).getByRole('checkbox', { name: /Materiality has been reassessed/ })
}

function recordButton(name = 'Record evaluation run'): HTMLElement {
  return within(runForm()).getByRole('button', { name })
}

function strategyForm(): HTMLElement {
  return screen.getByRole('form', { name: 'Answer the strategy prompt' })
}

function posts(): string[] {
  return requested().filter((request) => request.startsWith('POST'))
}

function gets(): string[] {
  return requested().filter((request) => request.startsWith('GET'))
}

// ---- recording an evaluation run ----

test('a run cannot be recorded until the reassessment of materiality is stated', async () => {
  await open(clearNoRun)
  expect(reassessed()).not.toBeChecked()
  expect(recordButton()).toBeDisabled()
  fireEvent.click(recordButton())
  fireEvent.submit(runForm())
  expect(posts()).toEqual([])

  fireEvent.click(reassessed())
  expect(reassessed()).toBeChecked()
  expect(recordButton()).toBeEnabled()
})

test('recording a run sends only the reassessment, then reads the evaluation again', async () => {
  await open(clearNoRun, {
    ...evaluationAnswersInTurn(clearNoRun, runCurrent, inTurn),
    [runsPath(clearNoRun)]: answered(201, runRecorded),
  })
  expect(panel('Evaluation runs')).toHaveTextContent('No evaluation run has been recorded yet.')
  expect(gets()).toHaveLength(6)

  fireEvent.click(reassessed())
  fireEvent.click(recordButton())
  expect(await screen.findByText('Recorded: run 1.')).toBeInTheDocument()

  // No figure is sent: the backend computes and stores them.
  expect(sent()).toEqual([
    {
      request: `POST /api/engagements/${clearNoRun.engagement.id}/evaluation/runs`,
      body: { materiality_reassessed: true },
      contentType: 'application/json',
    },
  ])
  // The screen is read again in full, and shows what the backend now holds.
  const history = await screen.findByRole('table', { name: 'Evaluation runs, newest first' })
  expect(gets()).toHaveLength(12)
  expect(within(history).getByRole('rowheader')).toHaveTextContent('Run 1')
  expect(within(history).getByText('Current')).toBeInTheDocument()
  expect(panel('Evaluation runs')).toHaveTextContent(
    'Latest run:Currentthe latest run describes the evaluation as it stands',
  )
  // The statement is asked for afresh for the next run.
  expect(reassessed()).not.toBeChecked()
  expect(recordButton()).toBeDisabled()
  expect(screen.getByText('Recorded: run 1.')).toBeInTheDocument()
})

test('the screen does not blank while it reads again after a run', async () => {
  const pending = deferred()
  await open(clearNoRun, { [runsPath(clearNoRun)]: pending.answer })
  fireEvent.click(reassessed())
  fireEvent.click(recordButton())
  await act(async () => {
    pending.arrive(answered(201, runRecorded))
    await pending.answer
  })
  expect(await screen.findByText('Recorded: run 1.')).toBeInTheDocument()
  expect(screen.queryByText('Loading the evaluation…')).not.toBeInTheDocument()
  expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
})

test('a run the backend refuses is shown in its words, and nothing is read again', async () => {
  await open(spineDown, {
    [runsPath(spineDown)]: refusal(refusals.runNotEvaluable.status, refusals.runNotEvaluable.body),
  })
  fireEvent.click(reassessed())
  fireEvent.click(recordButton())
  const alert = await within(runForm()).findByRole('alert')
  expect(alert).toHaveTextContent('The run was not recorded')
  expect(alert).toHaveTextContent(refusals.runNotEvaluable.body.detail)
  expect(refusals.runNotEvaluable.body.detail).toContain(
    'the effects of M-1, M-2, M-3, M-4, M-6 cannot be determined',
  )
  expect(alert).toHaveTextContent(
    `/api/engagements/${spineDown.engagement.id}/evaluation/runs answered 409`,
  )
  expect(screen.queryByText(/^Recorded: run/)).not.toBeInTheDocument()
  expect(gets()).toHaveLength(6)
  // The statement stays ticked so the run can be tried again.
  expect(reassessed()).toBeChecked()
  expect(recordButton()).toBeEnabled()
})

test('with no thresholds a run is refused for the backend’s reason', async () => {
  await open(empty, {
    [runsPath(empty)]: refusal(refusals.runNoThresholds.status, refusals.runNoThresholds.body),
  })
  fireEvent.click(reassessed())
  fireEvent.click(recordButton())
  const alert = await within(runForm()).findByRole('alert')
  expect(alert).toHaveTextContent(refusals.runNoThresholds.body.detail)
  expect(refusals.runNoThresholds.body.detail).toContain('no thresholds have been set')
})

test('a validation refusal of a run names the field and what is wrong', async () => {
  await open(clearNoRun, {
    [runsPath(clearNoRun)]: refusal(
      refusals.runNotReassessed.status,
      refusals.runNotReassessed.body,
    ),
  })
  fireEvent.click(reassessed())
  fireEvent.click(recordButton())
  const alert = await within(runForm()).findByRole('alert')
  expect(alert).toHaveTextContent('materiality_reassessed: Input should be True')
  expect(alert).toHaveTextContent('answered 422')
})

test('a backend that cannot be reached is explained, and the run can be tried again', async () => {
  await open(clearNoRun)
  failApi()
  fireEvent.click(reassessed())
  fireEvent.click(recordButton())
  const alert = await within(runForm()).findByRole('alert')
  expect(alert).toHaveTextContent('The backend could not be reached.')

  mockApi({ ...evaluationAnswers(runCurrent), [runsPath(clearNoRun)]: answered(201, runRecorded) })
  fireEvent.click(recordButton())
  expect(await screen.findByText('Recorded: run 1.')).toBeInTheDocument()
  expect(within(runForm()).queryByRole('alert')).not.toBeInTheDocument()
  expect(posts()).toHaveLength(1)
})

test('a run goes out once, however many times it is confirmed while it is processing', async () => {
  const pending = deferred()
  await open(clearNoRun, { [runsPath(clearNoRun)]: pending.answer })
  fireEvent.click(reassessed())
  const button = recordButton()
  fireEvent.click(button)
  fireEvent.click(button)
  fireEvent.submit(runForm())
  fireEvent.submit(runForm())
  expect(posts()).toHaveLength(1)

  expect(recordButton('Recording…')).toBeDisabled()
  expect(reassessed()).toBeDisabled()
  expect(screen.queryByText(/^Recorded: run/)).not.toBeInTheDocument()

  await act(async () => {
    pending.arrive(answered(201, runRecorded))
    await pending.answer
  })
  expect(await screen.findByText('Recorded: run 1.')).toBeInTheDocument()
  expect(posts()).toHaveLength(1)
})

// ---- answering the strategy prompt ----

test('the strategy prompt cannot be answered until a person says which way it went', async () => {
  await open(strategyRequired)
  const form = strategyForm()
  expect(within(form).getByRole('radio', { name: 'Yes, they were revised' })).not.toBeChecked()
  expect(within(form).getByRole('radio', { name: 'No, they were not revised' })).not.toBeChecked()
  expect(within(form).getByRole('button', { name: 'Record the answer' })).toBeDisabled()
  fireEvent.submit(form)
  expect(posts()).toEqual([])
  // The note is offered and is not required.
  expect(within(form).getByRole('textbox', { name: /Note/ })).not.toBeRequired()
})

test('answering sends whether the strategy was revised and the note, then reads again', async () => {
  await open(strategyRequired, {
    ...evaluationAnswersInTurn(strategyRequired, strategyRecorded, inTurn),
    [strategyPath(strategyRequired)]: answered(201, strategyResponse),
  })
  const form = strategyForm()
  fireEvent.click(within(form).getByRole('radio', { name: 'No, they were not revised' }))
  fireEvent.change(within(form).getByRole('textbox', { name: /Note/ }), {
    target: { value: '  Revisited with the partner; no change needed  ' },
  })
  fireEvent.click(within(form).getByRole('button', { name: 'Record the answer' }))

  expect(
    await screen.findByText('Recorded: the answer to the strategy prompt.'),
  ).toBeInTheDocument()
  expect(sent()).toEqual([
    {
      request: `POST /api/engagements/${strategyRequired.engagement.id}/evaluation/strategy-responses`,
      body: { strategy_revised: false, note: 'Revisited with the partner; no change needed' },
      contentType: 'application/json',
    },
  ])
  // Read again: the backend now says the prompt is answered, so the form is gone.
  expect(await screen.findByText('answered on these figures')).toBeInTheDocument()
  expect(screen.queryByRole('form', { name: 'Answer the strategy prompt' })).toBeNull()
  expect(gets()).toHaveLength(12)
  expect(screen.getByText('Recorded: the answer to the strategy prompt.')).toBeInTheDocument()
})

test('an answer with no note sends no note', async () => {
  await open(strategyRequired, {
    [strategyPath(strategyRequired)]: answered(201, strategyResponse),
  })
  const form = strategyForm()
  fireEvent.click(within(form).getByRole('radio', { name: 'Yes, they were revised' }))
  fireEvent.change(within(form).getByRole('textbox', { name: /Note/ }), {
    target: { value: '   ' },
  })
  fireEvent.click(within(form).getByRole('button', { name: 'Record the answer' }))
  await screen.findByText('Recorded: the answer to the strategy prompt.')
  expect(sent().map((entry) => entry.body)).toEqual([{ strategy_revised: true }])
})

test('an answer the backend refuses is shown in its words', async () => {
  await open(strategyRequired, {
    [strategyPath(strategyRequired)]: refusal(
      refusals.strategyAlreadyAnswered.status,
      refusals.strategyAlreadyAnswered.body,
    ),
  })
  const form = strategyForm()
  fireEvent.click(within(form).getByRole('radio', { name: 'Yes, they were revised' }))
  fireEvent.click(within(form).getByRole('button', { name: 'Record the answer' }))
  const alert = await within(form).findByRole('alert')
  expect(alert).toHaveTextContent('The answer was not recorded')
  expect(alert).toHaveTextContent('the strategy prompt is already answered on these figures')
  expect(alert).toHaveTextContent('answered 409')
  expect(screen.queryByText(/^Recorded: the answer/)).not.toBeInTheDocument()
  // The choice is kept.
  expect(within(form).getByRole('radio', { name: 'Yes, they were revised' })).toBeChecked()
  expect(gets()).toHaveLength(6)
})

test('an answer goes out once while it is processing', async () => {
  const pending = deferred()
  await open(strategyRequired, { [strategyPath(strategyRequired)]: pending.answer })
  const form = strategyForm()
  fireEvent.click(within(form).getByRole('radio', { name: 'No, they were not revised' }))
  const button = within(form).getByRole('button', { name: 'Record the answer' })
  fireEvent.click(button)
  fireEvent.click(button)
  fireEvent.submit(form)
  expect(posts()).toHaveLength(1)
  expect(within(form).getByRole('button', { name: 'Recording…' })).toBeDisabled()
  expect(within(form).getByRole('radio', { name: 'Yes, they were revised' })).toBeDisabled()
  expect(within(form).getByRole('textbox', { name: /Note/ })).toBeDisabled()

  await act(async () => {
    pending.arrive(answered(201, strategyResponse))
    await pending.answer
  })
  expect(
    await screen.findByText('Recorded: the answer to the strategy prompt.'),
  ).toBeInTheDocument()
  expect(posts()).toHaveLength(1)
})

// ---- nothing else is ever sent ----

test('the only writes this screen can send are a run and a strategy answer', async () => {
  await open(strategyRequired, {
    [runsPath(strategyRequired)]: answered(201, runRecorded),
    [strategyPath(strategyRequired)]: answered(201, strategyResponse),
  })
  fireEvent.click(reassessed())
  fireEvent.click(recordButton())
  await screen.findByText(/^Recorded: run/)
  const form = strategyForm()
  fireEvent.click(within(form).getByRole('radio', { name: 'Yes, they were revised' }))
  fireEvent.click(within(form).getByRole('button', { name: 'Record the answer' }))
  await screen.findByText('Recorded: the answer to the strategy prompt.')
  const id = strategyRequired.engagement.id
  expect(posts()).toEqual([
    `POST /api/engagements/${id}/evaluation/runs`,
    `POST /api/engagements/${id}/evaluation/strategy-responses`,
  ])
  expect(requested().filter((request) => /acknowledg|conclusions\//.test(request))).toEqual([])
})

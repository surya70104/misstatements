// The qualitative checklist and escalation on the screens (spec sections 5 and 10.2;
// acceptance 8; backend D59): the checklist on the misstatement detail, the Escalated mark
// on the schedule, and the escalated items on the evaluation screen. Every answer and every
// refusal below is the backend's real one, captured by
// backend/tests/test_frontend_fixtures.py as one misstatement was escalated and cleared.
import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import type { Misstatement } from '../src/api'
import { NOTE_MAX_LENGTH } from '../src/labels'
import { EvaluationPage } from '../src/pages/EvaluationPage'
import { MisstatementPage } from '../src/pages/MisstatementPage'
import { SchedulePage } from '../src/pages/SchedulePage'
import { corrected, detailPath, raised } from './detailFixtures'
import { clearNoRun, evaluationAnswers } from './evaluationFixtures'
import { answered, deferred, failApi, mockApi, refusal, requested, sent } from './mockApi'
import {
  clearPath,
  cleared,
  detailClear,
  detailCleared,
  detailEscalated,
  detailReasonChanged,
  engagement,
  evaluation,
  evaluationScreen,
  misstatements,
  reasonChanged,
  recorded,
  recordPath,
  refusals,
} from './qualitativeFixtures'
import { SCHEDULE, scheduleAnswers } from './scheduleFixtures'

afterEach(() => {
  vi.unstubAllGlobals()
})

const RELATED_PARTY = 'relates to a related party transaction'
const FRAUD = 'relates to a fraud or a suspected fraud'
const FIRST_REASON = 'Sale to a firm owned by a director; see E-12'
const SECOND_REASON = "Director's firm; pricing not at arm's length"
const CLEARING_REASON = 'The buyer is not a related party: E-12 revised'

async function open(misstatement: Misstatement, answers: Record<string, unknown> = {}) {
  mockApi({ [detailPath(misstatement)]: misstatement, ...answers })
  const view = render(<MisstatementPage id={misstatement.id} />)
  await screen.findByRole('heading', { level: 1 })
  return view
}

function panel(): HTMLElement {
  return screen.getByRole('region', { name: 'Qualitative factors' })
}

function rows(): HTMLElement[] {
  return within(within(panel()).getByRole('list', { name: 'Qualitative checklist' })).getAllByRole(
    'listitem',
  )
}

/** The row of the checklist that carries a factor's wording. */
function rowOf(text: string): HTMLElement {
  const row = rows().find((candidate) => candidate.textContent.includes(text))
  if (row === undefined) throw new Error(`no row of the checklist reads: ${text}`)
  return row
}

function choose(text: string, button: 'Record' | 'New reason' | 'Clear') {
  fireEvent.click(within(rowOf(text)).getByRole('button', { name: button }))
}

function typeReason(text: string) {
  fireEvent.change(within(panel()).getByRole('textbox'), { target: { value: text } })
}

function confirmButton(name: string): HTMLElement {
  return within(panel()).getByRole('button', { name })
}

function history(): HTMLElement[] {
  const list = within(panel()).queryByRole('list', { name: 'History of the checklist' })
  return list === null ? [] : within(list).getAllByRole('listitem')
}

/** The pills beside the reference at the top of the page. */
function headerPills(): HTMLElement {
  return screen.getByRole('heading', { level: 1 }).parentElement as HTMLElement
}

function posts(): string[] {
  return requested().filter((request) => request.startsWith('POST'))
}

// ---- the checklist as it is read ----

test('the checklist is the seven factors, in the backend’s order and words', async () => {
  await open(detailClear)
  const checklist = detailClear.qualitative.checklist ?? []
  expect(checklist).toHaveLength(7)
  expect(rows()).toHaveLength(7)
  rows().forEach((row, index) => {
    expect(row).toHaveTextContent(checklist[index]?.text ?? 'missing')
  })
  // The specification's seven (section 5), as the backend words them.
  for (const words of [
    'loan covenant',
    'a change in earnings or a trend',
    'the eleven Schedule III ratios',
    'a fraud or a suspected fraud',
    'a related party transaction',
    'segment information, or management remuneration',
    'turns a loss into a profit, or the reverse',
  ]) {
    expect(panel()).toHaveTextContent(words)
  }
})

test('a misstatement with no factor recorded is not escalated, and every factor can be recorded', async () => {
  await open(detailClear)
  expect(panel()).toHaveTextContent('Not escalated')
  expect(panel()).toHaveTextContent('No qualitative factor is recorded against this misstatement.')
  expect(headerPills()).toHaveTextContent('Clearly trivial')
  expect(headerPills()).not.toHaveTextContent('Escalated')
  for (const row of rows()) {
    expect(row).toHaveTextContent('Not recorded')
    expect(within(row).getByRole('button', { name: 'Record' })).toBeEnabled()
    expect(within(row).queryByRole('button', { name: 'Clear' })).not.toBeInTheDocument()
  }
  expect(history()).toEqual([])
  // Nothing is asked for until a factor is chosen.
  expect(screen.queryByRole('form')).not.toBeInTheDocument()
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
})

test('each button is described by the factor it acts on', async () => {
  await open(detailClear)
  const button = within(rowOf(RELATED_PARTY)).getByRole('button', { name: 'Record' })
  expect(button).toHaveAccessibleDescription(RELATED_PARTY)
})

test('an escalated misstatement says so, with the factor, its reason and who recorded it', async () => {
  await open(detailEscalated)
  // The band is still the amount's: clearly trivial, and escalated beside it.
  expect(headerPills()).toHaveTextContent('Clearly trivial')
  expect(headerPills()).toHaveTextContent('Escalated')
  expect(panel()).toHaveTextContent(
    'A qualitative factor is recorded, so this misstatement is listed individually whatever its amount.',
  )
  const row = rowOf(RELATED_PARTY)
  expect(row).toHaveTextContent('Recorded')
  expect(row).toHaveTextContent(`Reason: ${FIRST_REASON}`)
  expect(row).toHaveTextContent('by manager@firm')
  expect(within(row).getByRole('button', { name: 'New reason' })).toBeEnabled()
  expect(within(row).getByRole('button', { name: 'Clear' })).toBeEnabled()
  expect(within(row).queryByRole('button', { name: 'Record' })).not.toBeInTheDocument()
  // The other six are still open to be recorded.
  expect(within(panel()).getAllByRole('button', { name: 'Record' })).toHaveLength(6)
  expect(history()).toHaveLength(1)
  expect(history()[0]).toHaveTextContent('Recorded')
  expect(history()[0]).toHaveTextContent('entry 1')
  // The backend's own explanation of escalation is shown as it was sent.
  expect(panel()).toHaveTextContent(detailEscalated.qualitative.escalation_basis ?? 'missing')
})

test('the checklist is offered on a misstatement in a final state as well', async () => {
  await open(corrected)
  expect(within(panel()).getAllByRole('button', { name: 'Record' })).toHaveLength(7)
})

// ---- recording a factor ----

test('a factor cannot be recorded without a reason', async () => {
  await open(detailClear)
  choose(RELATED_PARTY, 'Record')
  const form = screen.getByRole('form', { name: 'Record a qualitative factor' })
  expect(form).toHaveTextContent(RELATED_PARTY)
  expect(form).toHaveTextContent('The misstatement is escalated from then on.')
  const reason = within(form).getByRole('textbox', { name: /Reason this factor applies/ })
  expect(reason).toBeRequired()
  expect(reason).toHaveAttribute('maxlength', String(NOTE_MAX_LENGTH))
  expect(confirmButton('Confirm: record factor')).toBeDisabled()

  // Spaces are not a reason.
  typeReason('   \n ')
  expect(confirmButton('Confirm: record factor')).toBeDisabled()
  fireEvent.click(confirmButton('Confirm: record factor'))
  fireEvent.submit(form)
  expect(posts()).toEqual([])

  typeReason(FIRST_REASON)
  expect(confirmButton('Confirm: record factor')).toBeEnabled()
})

test('recording sends the factor and its reason, then shows the checklist as the backend holds it', async () => {
  await open(detailClear, { [recordPath(detailClear)]: answered(201, recorded) })
  choose(RELATED_PARTY, 'Record')
  typeReason(`  ${FIRST_REASON}  `)
  fireEvent.click(confirmButton('Confirm: record factor'))

  expect(await screen.findByText('Factor recorded: M-2 is escalated.')).toBeInTheDocument()
  // The reason goes out without the spaces around it; who acts is never sent.
  expect(sent()).toEqual([
    {
      request: `POST /api/misstatements/${detailClear.id}/qualitative`,
      body: { factor: 'related_party', note: FIRST_REASON },
      contentType: 'application/json',
    },
  ])
  // The answer to the write is the checklist: it is shown without a second read.
  expect(requested()).toEqual([
    `GET /api/misstatements/${detailClear.id}`,
    `POST /api/misstatements/${detailClear.id}/qualitative`,
  ])
  expect(headerPills()).toHaveTextContent('Escalated')
  // The amount has not changed, so neither has the band.
  expect(headerPills()).toHaveTextContent('Clearly trivial')
  const row = rowOf(RELATED_PARTY)
  expect(row).toHaveTextContent(`Reason: ${FIRST_REASON}`)
  expect(row).toHaveTextContent('by manager@firm')
  expect(within(row).getByRole('button', { name: 'Clear' })).toBeInTheDocument()
  expect(history()).toHaveLength(1)
  expect(screen.queryByRole('form')).not.toBeInTheDocument()
  // What is shown is what the backend then answers when the misstatement is read again.
  expect(recorded.checklist).toEqual(detailEscalated.qualitative.checklist)
  expect(recorded.history).toEqual(detailEscalated.qualitative.history)
})

test('cancelling closes the form and sends nothing', async () => {
  await open(detailClear)
  choose(FRAUD, 'Record')
  typeReason('typed and abandoned')
  fireEvent.click(within(panel()).getByRole('button', { name: 'Cancel' }))
  expect(screen.queryByRole('form')).not.toBeInTheDocument()
  expect(posts()).toEqual([])
  expect(panel()).toHaveTextContent('Not escalated')
})

test('choosing another factor starts its reason afresh', async () => {
  await open(detailClear)
  choose(FRAUD, 'Record')
  typeReason('typed for fraud')
  expect(within(rowOf(FRAUD)).getByRole('button', { name: 'Record' })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  choose(RELATED_PARTY, 'Record')
  expect(within(panel()).getByRole('textbox')).toHaveValue('')
  expect(screen.getByRole('form')).toHaveTextContent(RELATED_PARTY)
  expect(within(rowOf(FRAUD)).getByRole('button', { name: 'Record' })).toHaveAttribute(
    'aria-pressed',
    'false',
  )
})

// ---- a new reason ----

test('a new reason is recorded as a further entry, and the first one is kept', async () => {
  await open(detailEscalated, { [recordPath(detailEscalated)]: answered(201, reasonChanged) })
  choose(RELATED_PARTY, 'New reason')
  const form = screen.getByRole('form', { name: 'Record a new reason for a qualitative factor' })
  expect(form).toHaveTextContent(`Reason recorded now: ${FIRST_REASON}`)
  expect(confirmButton('Confirm: new reason')).toBeDisabled()
  typeReason(SECOND_REASON)
  fireEvent.click(confirmButton('Confirm: new reason'))

  expect(await screen.findByText('Reason changed: M-2 is escalated.')).toBeInTheDocument()
  expect(sent().map((entry) => entry.body)).toEqual([
    { factor: 'related_party', note: SECOND_REASON },
  ])
  expect(rowOf(RELATED_PARTY)).toHaveTextContent(`Reason: ${SECOND_REASON}`)
  expect(rowOf(RELATED_PARTY)).not.toHaveTextContent(FIRST_REASON)
  expect(history()).toHaveLength(2)
  expect(history()[0]).toHaveTextContent(`Reason: ${FIRST_REASON}`)
  expect(history()[1]).toHaveTextContent(`Reason: ${SECOND_REASON}`)
  expect(headerPills()).toHaveTextContent('Escalated')
})

// ---- clearing a factor ----

test('a factor cannot be cleared without a reason', async () => {
  await open(detailEscalated)
  choose(RELATED_PARTY, 'Clear')
  const form = screen.getByRole('form', { name: 'Clear a qualitative factor' })
  expect(within(form).getByRole('textbox', { name: /Reason for clearing/ })).toBeRequired()
  expect(confirmButton('Confirm: clear factor')).toBeDisabled()
  typeReason(' \t ')
  expect(confirmButton('Confirm: clear factor')).toBeDisabled()
  fireEvent.submit(form)
  expect(posts()).toEqual([])
})

test('clearing sends the reason, ends the escalation and keeps every entry', async () => {
  await open(detailReasonChanged, {
    [clearPath(detailReasonChanged, 'related_party')]: answered(201, cleared),
  })
  expect(headerPills()).toHaveTextContent('Escalated')
  expect(history()).toHaveLength(2)
  choose(RELATED_PARTY, 'Clear')
  typeReason(CLEARING_REASON)
  fireEvent.click(confirmButton('Confirm: clear factor'))

  expect(await screen.findByText('Factor cleared: M-2 is no longer escalated.')).toBeInTheDocument()
  expect(sent()).toEqual([
    {
      request: `POST /api/misstatements/${detailReasonChanged.id}/qualitative/related_party/clear`,
      body: { note: CLEARING_REASON },
      contentType: 'application/json',
    },
  ])
  expect(headerPills()).not.toHaveTextContent('Escalated')
  expect(panel()).toHaveTextContent('Not escalated')
  const row = rowOf(RELATED_PARTY)
  expect(row).toHaveTextContent('Not recorded')
  expect(row).not.toHaveTextContent(SECOND_REASON)
  expect(within(row).getByRole('button', { name: 'Record' })).toBeEnabled()
  // Nothing is removed: the two recordings and the clearing are all in the history.
  expect(history()).toHaveLength(3)
  expect(history()[0]).toHaveTextContent(`Reason: ${FIRST_REASON}`)
  expect(history()[1]).toHaveTextContent(`Reason: ${SECOND_REASON}`)
  expect(history()[2]).toHaveTextContent('Cleared')
  expect(history()[2]).toHaveTextContent(`Reason for clearing: ${CLEARING_REASON}`)
  expect(cleared.checklist).toEqual(detailCleared.qualitative.checklist)
  expect(cleared.history).toEqual(detailCleared.qualitative.history)
})

// ---- backend refusals ----

test('a factor already recorded with the same reason is refused in the backend’s words', async () => {
  await open(detailEscalated, {
    [recordPath(detailEscalated)]: refusal(
      refusals.alreadyRecorded.status,
      refusals.alreadyRecorded.body,
    ),
  })
  choose(RELATED_PARTY, 'New reason')
  typeReason(FIRST_REASON)
  fireEvent.click(confirmButton('Confirm: new reason'))

  const alert = await within(panel()).findByRole('alert')
  expect(alert).toHaveTextContent('Nothing was recorded')
  expect(alert).toHaveTextContent(refusals.alreadyRecorded.body.detail)
  expect(alert).toHaveTextContent(
    `/api/misstatements/${detailEscalated.id}/qualitative answered 409`,
  )
  expect(screen.queryByText(/^Reason changed:/)).not.toBeInTheDocument()
  expect(history()).toHaveLength(1)
  // The form is kept as it was, so nothing has to be typed again.
  expect(within(panel()).getByRole('textbox')).toHaveValue(FIRST_REASON)
  expect(confirmButton('Confirm: new reason')).toBeEnabled()
})

test('clearing a factor someone else has already cleared is refused, and nothing changes', async () => {
  await open(detailEscalated, {
    [clearPath(detailEscalated, 'related_party')]: refusal(
      refusals.notRecorded.status,
      refusals.notRecorded.body,
    ),
  })
  choose(RELATED_PARTY, 'Clear')
  typeReason('Cleared twice')
  fireEvent.click(confirmButton('Confirm: clear factor'))
  const alert = await within(panel()).findByRole('alert')
  expect(alert).toHaveTextContent(refusals.notRecorded.body.detail)
  expect(alert).toHaveTextContent('answered 409')
  expect(headerPills()).toHaveTextContent('Escalated')
})

test('a reason the backend finds blank is named with its problem', async () => {
  await open(detailClear, {
    [recordPath(detailClear)]: refusal(refusals.blankNote.status, refusals.blankNote.body),
  })
  choose(FRAUD, 'Record')
  typeReason('x')
  fireEvent.click(confirmButton('Confirm: record factor'))
  const alert = await within(panel()).findByRole('alert')
  expect(alert).toHaveTextContent('note: String should have at least 1 character')
  expect(alert).toHaveTextContent('answered 422')
  expect(panel()).toHaveTextContent('Not escalated')
})

test('a backend that cannot be reached is explained, and the factor can be sent again', async () => {
  await open(detailClear)
  failApi()
  choose(RELATED_PARTY, 'Record')
  typeReason(FIRST_REASON)
  fireEvent.click(confirmButton('Confirm: record factor'))
  const alert = await within(panel()).findByRole('alert')
  expect(alert).toHaveTextContent('The backend could not be reached.')
  expect(panel()).toHaveTextContent('Not escalated')

  mockApi({ [recordPath(detailClear)]: answered(201, recorded) })
  fireEvent.click(confirmButton('Confirm: record factor'))
  expect(await screen.findByText('Factor recorded: M-2 is escalated.')).toBeInTheDocument()
  expect(within(panel()).queryByRole('alert')).not.toBeInTheDocument()
  expect(posts()).toHaveLength(1)
})

test('choosing a factor again clears the last refusal', async () => {
  await open(detailClear, { [recordPath(detailClear)]: refusal(500) })
  choose(FRAUD, 'Record')
  typeReason('x')
  fireEvent.click(confirmButton('Confirm: record factor'))
  await within(panel()).findByRole('alert')
  choose(RELATED_PARTY, 'Record')
  expect(within(panel()).queryByRole('alert')).not.toBeInTheDocument()
})

// ---- duplicate submissions ----

test('a factor goes out once, however many times it is confirmed while it is processing', async () => {
  const pending = deferred()
  await open(detailClear, { [recordPath(detailClear)]: pending.answer })
  choose(RELATED_PARTY, 'Record')
  typeReason(FIRST_REASON)
  const form = screen.getByRole('form', { name: 'Record a qualitative factor' })
  const confirm = confirmButton('Confirm: record factor')

  fireEvent.click(confirm)
  fireEvent.click(confirm)
  fireEvent.submit(form)
  expect(posts()).toHaveLength(1)

  // While it is processing every control of the checklist says so and none can be used.
  expect(within(panel()).getByRole('button', { name: 'Recording…' })).toBeDisabled()
  expect(within(panel()).getByRole('textbox')).toBeDisabled()
  for (const button of within(panel()).getAllByRole('button')) expect(button).toBeDisabled()
  fireEvent.click(within(panel()).getByRole('button', { name: 'Cancel' }))
  expect(screen.getByRole('form', { name: 'Record a qualitative factor' })).toBeInTheDocument()

  await act(async () => {
    pending.arrive(answered(201, recorded))
    await pending.answer
  })
  expect(await screen.findByText('Factor recorded: M-2 is escalated.')).toBeInTheDocument()
  expect(posts()).toHaveLength(1)
  expect(history()).toHaveLength(1)
})

// ---- another misstatement ----

test('a reason half-typed on one misstatement does not carry over to another', async () => {
  mockApi({ [detailPath(detailClear)]: detailClear, [detailPath(raised)]: raised })
  const page = render(<MisstatementPage id={detailClear.id} />)
  await screen.findByRole('heading', { level: 1, name: 'M-2' })
  choose(FRAUD, 'Record')
  typeReason('typed on M-2')
  page.rerender(<MisstatementPage id={raised.id} />)
  await screen.findByRole('heading', { level: 1, name: 'M-1' })
  expect(screen.queryByRole('form')).not.toBeInTheDocument()
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  expect(posts()).toEqual([])
})

// ---- the schedule ----

function scheduleRow(ref: string): HTMLElement {
  const table = screen.getByRole('table', { name: 'Schedule of misstatements' })
  return within(table).getByRole('row', { name: new RegExp(`^${ref} `) })
}

test('the schedule marks an escalated item, whatever its amount', async () => {
  mockApi(scheduleAnswers(engagement.id, { engagement, misstatements, evaluation }))
  render(<SchedulePage id={engagement.id} />)
  await screen.findByRole('heading', { level: 1 })

  // M-2 is below the clearly-trivial threshold and escalated: both are shown.
  const small = scheduleRow('M-2')
  expect(small).toHaveTextContent('Clearly trivial')
  expect(within(small).getByText('Escalated')).toBeInTheDocument()
  expect(small).toHaveTextContent(
    'Listed individually whatever its amount: 1 qualitative factor recorded',
  )
  // M-1 is larger and has no factor recorded: it is not marked.
  const ordinary = scheduleRow('M-1')
  expect(ordinary).toHaveTextContent('Accumulated')
  expect(within(ordinary).queryByText('Escalated')).not.toBeInTheDocument()
})

test('a schedule with no factor recorded marks nothing as escalated', async () => {
  mockApi(SCHEDULE)
  const id = Object.keys(SCHEDULE)[0]?.split('/')[3] ?? ''
  render(<SchedulePage id={id} />)
  await screen.findByRole('heading', { level: 1 })
  expect(screen.getByRole('table', { name: 'Schedule of misstatements' })).not.toHaveTextContent(
    'Escalated',
  )
})

// ---- the evaluation ----

test('the evaluation lists an escalated item individually, and sign-off is not blocked by it', async () => {
  mockApi(evaluationAnswers(evaluationScreen))
  render(<EvaluationPage id={evaluationScreen.engagement.id} />)
  await screen.findByRole('heading', { level: 1 })

  const individual = screen.getByRole('region', { name: 'Individual items' })
  expect(individual).toHaveTextContent('Present')
  const listed = within(within(individual).getByRole('list', { name: 'Escalated items' }))
    .getAllByRole('listitem')
    .map((item) => item.textContent)
  expect(listed).toEqual(['M-2: Clearly trivial by amount; 1 factor recorded'])
  expect(individual).toHaveTextContent(
    evaluationScreen.evaluation.tests.individual.escalation_basis,
  )
  // Escalation lists an item; it is not one of the gates (spec section 7).
  expect(evaluationScreen.evaluation.sign_off.blocked).toBe(false)
  expect(screen.getByRole('region', { name: 'Sign-off' })).toHaveTextContent('Open')
})

test('an evaluation with no factor recorded lists no escalated item', async () => {
  mockApi(evaluationAnswers(clearNoRun))
  render(<EvaluationPage id={clearNoRun.engagement.id} />)
  await screen.findByRole('heading', { level: 1 })
  expect(screen.queryByRole('list', { name: 'Escalated items' })).not.toBeInTheDocument()
})

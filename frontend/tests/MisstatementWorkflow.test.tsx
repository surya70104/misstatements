// The moves a misstatement can make from its detail page (spec section 3.3):
//   raised -> communicated -> corrected | refused | withdrawn
// Every answer and every refusal below is the backend's real one, captured by
// backend/tests/test_frontend_fixtures.py as the same misstatement was moved.
import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import type { Misstatement } from '../src/api'
import { REASON_MAX_LENGTH } from '../src/labels'
import { MisstatementPage } from '../src/pages/MisstatementPage'
import {
  communicated,
  communicatedJudgemental,
  communicatedProjected,
  corrected,
  detailPath,
  raised,
  refusals,
  refused,
  spineDown,
  toCommunicated,
  toCorrected,
  toRefused,
  toWithdrawn,
  transitionPath,
  withdrawn,
} from './detailFixtures'
import { answered, deferred, failApi, mockApi, refusal, requested, sent } from './mockApi'

afterEach(() => {
  vi.unstubAllGlobals()
})

const REFUSAL_REASON = 'Management considers the useful life appropriate'
const WITHDRAWAL_REASON = 'Sample re-performed: the errors were recorded in the correct period'

async function open(misstatement: Misstatement, answers: Record<string, unknown> = {}) {
  mockApi({ [detailPath(misstatement)]: misstatement, ...answers })
  const view = render(<MisstatementPage id={misstatement.id} />)
  await screen.findByRole('heading', { level: 1 })
  return view
}

function actions(): HTMLElement {
  return screen.getByRole('region', { name: 'Workflow actions' })
}

/** The moves offered, by the words on their buttons. */
function offered(): (string | null)[] {
  return within(actions())
    .queryAllByRole('button')
    .filter((button) => button.hasAttribute('aria-pressed'))
    .map((button) => button.textContent)
}

function choose(name: string) {
  fireEvent.click(within(actions()).getByRole('button', { name }))
}

function confirmButton(name: string): HTMLElement {
  return within(actions()).getByRole('button', { name })
}

function typeReason(text: string) {
  fireEvent.change(within(actions()).getByRole('textbox'), { target: { value: text } })
}

function currentState(): string | null {
  const term = within(screen.getByRole('region', { name: 'Identification' })).getByText(
    'Current state',
    { selector: 'dt' },
  )
  return term.nextElementSibling?.textContent ?? null
}

function historyLength(): number {
  return within(screen.getByRole('list', { name: 'State history' })).getAllByRole('listitem').length
}

function posts(): string[] {
  return requested().filter((request) => request.startsWith('POST'))
}

// ---- which moves are offered ----

test('a raised misstatement can only be communicated', async () => {
  await open(raised)
  expect(offered()).toEqual(['Mark as communicated'])
  expect(actions()).toHaveTextContent('This misstatement is raised.')
})

test('a communicated misstatement can be corrected, refused or withdrawn', async () => {
  await open(communicated)
  expect(offered()).toEqual(['Record correction', 'Record refusal', 'Withdraw'])
  expect(actions()).toHaveTextContent('This misstatement is communicated.')
})

test('a corrected, refused or withdrawn misstatement offers no move at all', async () => {
  for (const [misstatement, word] of [
    [corrected, 'corrected'],
    [refused, 'refused'],
    [withdrawn, 'withdrawn'],
  ] as const) {
    const view = await open(misstatement)
    expect(offered()).toEqual([])
    expect(within(actions()).queryAllByRole('button')).toEqual([])
    expect(actions()).toHaveTextContent(
      `This misstatement is ${word}, a final state. No further action is available, and the record cannot be edited.`,
    )
    view.unmount()
  }
})

test('nothing is sent until a move is chosen and confirmed', async () => {
  await open(communicated)
  expect(screen.queryByRole('form')).not.toBeInTheDocument()
  choose('Record correction')
  const form = screen.getByRole('form', { name: 'Record correction' })
  expect(form).toHaveTextContent(
    'Its adjustment is accepted in the Financial Spine and posts there.',
  )
  expect(within(actions()).getByRole('button', { name: 'Record correction' })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  expect(posts()).toEqual([])

  fireEvent.click(within(form).getByRole('button', { name: 'Cancel' }))
  expect(screen.queryByRole('form')).not.toBeInTheDocument()
  expect(posts()).toEqual([])
  expect(currentState()).toBe('Communicated')
})

// ---- raised -> communicated ----

test('communicating sends the move, then shows the record as the backend now holds it', async () => {
  await open(raised, { [transitionPath(raised)]: answered(201, toCommunicated) })
  expect(historyLength()).toBe(1)
  choose('Mark as communicated')
  // A move to communicated carries no reason, so none is asked for.
  expect(within(actions()).queryByRole('textbox')).not.toBeInTheDocument()
  fireEvent.click(confirmButton('Confirm: communicated'))

  expect(await screen.findByText('Recorded: M-1 is now communicated.')).toBeInTheDocument()
  expect(sent()).toEqual([
    {
      request: `POST /api/misstatements/${raised.id}/transitions`,
      body: { to: 'communicated' },
      contentType: 'application/json',
    },
  ])
  // The answer to the move is the record: it is shown without a second read.
  expect(requested()).toEqual([
    `GET /api/misstatements/${raised.id}`,
    `POST /api/misstatements/${raised.id}/transitions`,
  ])
  expect(currentState()).toBe('Communicated')
  expect(historyLength()).toBe(2)
  expect(screen.getByRole('list', { name: 'State history' })).toHaveTextContent('by manager@firm')
  // Communicating asks nothing of the Spine, so nothing is said about it.
  expect(toCommunicated.transition?.spine_decision).toBeNull()
  expect(actions()).not.toHaveTextContent('Financial Spine: adjustment')
  // The next moves are now the ones a communicated misstatement has.
  expect(offered()).toEqual(['Record correction', 'Record refusal', 'Withdraw'])
  expect(screen.queryByRole('form')).not.toBeInTheDocument()
})

// ---- communicated -> corrected ----

test('correcting records the move and reports what the Financial Spine did', async () => {
  await open(communicated, { [transitionPath(communicated)]: answered(201, toCorrected) })
  choose('Record correction')
  expect(within(actions()).queryByRole('textbox')).not.toBeInTheDocument()
  fireEvent.click(confirmButton('Confirm: corrected'))

  expect(await screen.findByText('Recorded: M-1 is now corrected.')).toBeInTheDocument()
  expect(sent().map((entry) => entry.body)).toEqual([{ to: 'corrected' }])
  expect(actions()).toHaveTextContent('Financial Spine: adjustment accepted.')
  expect(actions()).toHaveTextContent(
    'M-1 corrected: accepted by manager@firm in the Misstatements Rollup',
  )
  expect(currentState()).toBe('Corrected')
  expect(historyLength()).toBe(3)
  // Corrected is final: no move is offered any more.
  expect(offered()).toEqual([])
  expect(actions()).toHaveTextContent('This misstatement is corrected, a final state.')
})

// ---- communicated -> refused ----

test('a refusal cannot be confirmed without a reason', async () => {
  await open(communicatedJudgemental)
  choose('Record refusal')
  const reason = within(actions()).getByRole('textbox', { name: /Reason for refusal/ })
  expect(reason).toBeRequired()
  expect(reason).toHaveAttribute('maxlength', String(REASON_MAX_LENGTH))
  expect(confirmButton('Confirm: refused')).toBeDisabled()

  // Spaces are not a reason.
  typeReason('     ')
  expect(confirmButton('Confirm: refused')).toBeDisabled()
  fireEvent.click(confirmButton('Confirm: refused'))
  fireEvent.submit(screen.getByRole('form', { name: 'Record refusal' }))
  expect(posts()).toEqual([])

  typeReason(REFUSAL_REASON)
  expect(confirmButton('Confirm: refused')).toBeEnabled()
})

test('refusing sends the reason and shows it in the history', async () => {
  await open(communicatedJudgemental, {
    [transitionPath(communicatedJudgemental)]: answered(201, toRefused),
  })
  choose('Record refusal')
  typeReason(`  ${REFUSAL_REASON}  `)
  fireEvent.click(confirmButton('Confirm: refused'))

  expect(await screen.findByText('Recorded: M-2 is now refused.')).toBeInTheDocument()
  // The reason goes out as typed, without the spaces around it.
  expect(sent().map((entry) => entry.body)).toEqual([{ to: 'refused', reason: REFUSAL_REASON }])
  expect(currentState()).toBe('Refused')
  expect(historyLength()).toBe(3)
  expect(screen.getByRole('list', { name: 'State history' })).toHaveTextContent(
    `Reason for refusal: ${REFUSAL_REASON}`,
  )
  expect(actions()).toHaveTextContent('Financial Spine: adjustment refused.')
  expect(offered()).toEqual([])
})

// ---- communicated -> withdrawn ----

test('a withdrawal cannot be confirmed without a reason', async () => {
  await open(communicatedProjected)
  choose('Withdraw')
  expect(within(actions()).getByRole('textbox', { name: /Reason for withdrawal/ })).toBeRequired()
  expect(confirmButton('Confirm: withdrawn')).toBeDisabled()
  typeReason('\n \t')
  expect(confirmButton('Confirm: withdrawn')).toBeDisabled()
  fireEvent.submit(screen.getByRole('form', { name: 'Withdraw' }))
  expect(posts()).toEqual([])
})

test('withdrawing sends the reason and shows it in the history', async () => {
  await open(communicatedProjected, {
    [transitionPath(communicatedProjected)]: answered(201, toWithdrawn),
  })
  choose('Withdraw')
  typeReason(WITHDRAWAL_REASON)
  fireEvent.click(confirmButton('Confirm: withdrawn'))

  expect(await screen.findByText('Recorded: M-3 is now withdrawn.')).toBeInTheDocument()
  expect(sent().map((entry) => entry.body)).toEqual([
    { to: 'withdrawn', reason: WITHDRAWAL_REASON },
  ])
  expect(currentState()).toBe('Withdrawn')
  expect(screen.getByRole('list', { name: 'State history' })).toHaveTextContent(
    `Reason for withdrawal: ${WITHDRAWAL_REASON}`,
  )
  // The Spine records a withdrawal as a refused adjustment, and says which it was.
  expect(actions()).toHaveTextContent('Financial Spine: adjustment refused.')
  expect(actions()).toHaveTextContent('WITHDRAWN by the auditor, not a management refusal')
  expect(offered()).toEqual([])
})

test('changing the move chosen starts its reason afresh', async () => {
  await open(communicated)
  choose('Record refusal')
  typeReason('typed for a refusal')
  choose('Withdraw')
  const reason = within(actions()).getByRole('textbox', { name: /Reason for withdrawal/ })
  expect(reason).toHaveValue('')
  expect(confirmButton('Confirm: withdrawn')).toBeDisabled()
  choose('Record correction')
  expect(within(actions()).queryByRole('textbox')).not.toBeInTheDocument()
})

// ---- backend errors ----

test('a move the backend refuses is shown in its words, and nothing changes', async () => {
  // The page still shows "communicated", but someone else has corrected the misstatement.
  await open(communicated, {
    [transitionPath(communicated)]: refusal(
      refusals.fromFinalState.status,
      refusals.fromFinalState.body,
    ),
  })
  choose('Withdraw')
  typeReason('Not an error after all')
  fireEvent.click(confirmButton('Confirm: withdrawn'))

  const alert = await within(actions()).findByRole('alert')
  expect(alert).toHaveTextContent('The move was not recorded')
  expect(alert).toHaveTextContent(refusals.fromFinalState.body.detail)
  expect(alert).toHaveTextContent(`/api/misstatements/${communicated.id}/transitions answered 409`)
  expect(screen.queryByText(/^Recorded:/)).not.toBeInTheDocument()
  expect(currentState()).toBe('Communicated')
  expect(historyLength()).toBe(2)
  // The form is kept as it was, so nothing has to be typed again.
  expect(within(actions()).getByRole('textbox')).toHaveValue('Not an error after all')
  expect(confirmButton('Confirm: withdrawn')).toBeEnabled()
})

test('a validation refusal names what is wrong in the backend’s words', async () => {
  await open(communicated, {
    [transitionPath(communicated)]: refusal(
      refusals.refusalWithoutReason.status,
      refusals.refusalWithoutReason.body,
    ),
  })
  choose('Record refusal')
  typeReason('x')
  fireEvent.click(confirmButton('Confirm: refused'))
  const alert = await within(actions()).findByRole('alert')
  expect(alert).toHaveTextContent(
    'Value error, a refusal needs a reason: SA 450 paragraph 9, no blank refusals (spec section 2; acceptance 3)',
  )
  expect(alert).toHaveTextContent('answered 422')
})

test('a refused field is named with its problem', async () => {
  await open(communicated, {
    [transitionPath(communicated)]: refusal(refusals.blankReason.status, refusals.blankReason.body),
  })
  choose('Withdraw')
  typeReason('x')
  fireEvent.click(confirmButton('Confirm: withdrawn'))
  const alert = await within(actions()).findByRole('alert')
  expect(alert).toHaveTextContent('reason: String should have at least 1 character')
})

test('a Financial Spine that cannot be reached stops a correction, and says so', async () => {
  await open(spineDown, {
    [transitionPath(spineDown)]: refusal(refusals.spineDown.status, refusals.spineDown.body),
  })
  expect(offered()).toEqual(['Record correction', 'Record refusal', 'Withdraw'])
  choose('Record correction')
  fireEvent.click(confirmButton('Confirm: corrected'))
  const alert = await within(actions()).findByRole('alert')
  expect(alert).toHaveTextContent('the Financial Spine cannot be reached for the adjustments')
  expect(alert).toHaveTextContent('answered 503')
  expect(currentState()).toBe('Communicated')
})

test('a backend that cannot be reached is explained, and the move can be tried again', async () => {
  await open(raised)
  failApi()
  choose('Mark as communicated')
  fireEvent.click(confirmButton('Confirm: communicated'))
  const alert = await within(actions()).findByRole('alert')
  expect(alert).toHaveTextContent('The backend could not be reached.')
  expect(alert).not.toHaveTextContent('answered')
  expect(currentState()).toBe('Raised')

  mockApi({ [transitionPath(raised)]: answered(201, toCommunicated) })
  fireEvent.click(confirmButton('Confirm: communicated'))
  expect(await screen.findByText('Recorded: M-1 is now communicated.')).toBeInTheDocument()
  expect(within(actions()).queryByRole('alert')).not.toBeInTheDocument()
  expect(posts()).toHaveLength(1)
})

test('choosing a move again clears the last refusal', async () => {
  await open(communicated, {
    [transitionPath(communicated)]: refusal(
      refusals.fromFinalState.status,
      refusals.fromFinalState.body,
    ),
  })
  choose('Record correction')
  fireEvent.click(confirmButton('Confirm: corrected'))
  await within(actions()).findByRole('alert')
  choose('Record refusal')
  expect(within(actions()).queryByRole('alert')).not.toBeInTheDocument()
})

// ---- duplicate submissions ----

test('a move goes out once, however many times it is confirmed while it is processing', async () => {
  const pending = deferred()
  await open(raised, { [transitionPath(raised)]: pending.answer })
  choose('Mark as communicated')
  const form = screen.getByRole('form', { name: 'Mark as communicated' })
  const confirm = confirmButton('Confirm: communicated')

  fireEvent.click(confirm)
  fireEvent.click(confirm)
  fireEvent.submit(form)
  fireEvent.submit(form)
  expect(posts()).toHaveLength(1)

  // While it is processing every control says so and none can be used.
  const recording = within(actions()).getByRole('button', { name: 'Recording…' })
  expect(recording).toBeDisabled()
  expect(within(actions()).getByRole('button', { name: 'Cancel' })).toBeDisabled()
  expect(within(actions()).getByRole('button', { name: 'Mark as communicated' })).toBeDisabled()
  fireEvent.click(within(actions()).getByRole('button', { name: 'Cancel' }))
  expect(screen.getByRole('form', { name: 'Mark as communicated' })).toBeInTheDocument()
  expect(screen.queryByText(/^Recorded:/)).not.toBeInTheDocument()

  await act(async () => {
    pending.arrive(answered(201, toCommunicated))
    await pending.answer
  })
  expect(await screen.findByText('Recorded: M-1 is now communicated.')).toBeInTheDocument()
  expect(posts()).toHaveLength(1)
  expect(historyLength()).toBe(2)
})

test('the reason cannot be changed while the move is processing', async () => {
  const pending = deferred()
  await open(communicatedJudgemental, {
    [transitionPath(communicatedJudgemental)]: pending.answer,
  })
  choose('Record refusal')
  typeReason(REFUSAL_REASON)
  fireEvent.click(confirmButton('Confirm: refused'))
  expect(within(actions()).getByRole('textbox')).toBeDisabled()
  expect(offered()).toEqual(['Record correction', 'Record refusal', 'Withdraw'])
  for (const button of within(actions()).getAllByRole('button')) expect(button).toBeDisabled()

  await act(async () => {
    pending.arrive(answered(201, toRefused))
    await pending.answer
  })
  expect(await screen.findByText('Recorded: M-2 is now refused.')).toBeInTheDocument()
  expect(posts()).toHaveLength(1)
})

test('after a failed move the controls come back, so it can be sent again', async () => {
  // An answer with no body at all: the status is everything the screen has to show.
  await open(raised, { [transitionPath(raised)]: refusal(500) })
  choose('Mark as communicated')
  fireEvent.click(confirmButton('Confirm: communicated'))
  const alert = await within(actions()).findByRole('alert')
  expect(alert).toHaveTextContent(`/api/misstatements/${raised.id}/transitions answered 500`)
  expect(posts()).toHaveLength(1)
  expect(confirmButton('Confirm: communicated')).toBeEnabled()
  expect(within(actions()).getByRole('button', { name: 'Cancel' })).toBeEnabled()
})

// ---- another misstatement ----

test('a move half-chosen on one misstatement does not carry over to another', async () => {
  mockApi({
    [detailPath(communicatedJudgemental)]: communicatedJudgemental,
    [detailPath(communicatedProjected)]: communicatedProjected,
  })
  const page = render(<MisstatementPage id={communicatedJudgemental.id} />)
  await screen.findByRole('heading', { level: 1, name: 'M-2' })
  choose('Record refusal')
  typeReason('typed on M-2')
  page.rerender(<MisstatementPage id={communicatedProjected.id} />)
  await screen.findByRole('heading', { level: 1, name: 'M-3' })
  expect(screen.queryByRole('form')).not.toBeInTheDocument()
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  expect(posts()).toEqual([])
})

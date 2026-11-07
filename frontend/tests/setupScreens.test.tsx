// The screens that set an engagement up: create it, link it to the Financial Spine, set and
// revise its thresholds, record a misstatement, and read its event trail (register S1, S2,
// S11). Every answer and every refusal is the backend's real one, captured by
// backend/tests/test_frontend_fixtures.py.
import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { dateTime } from '../src/format'
import { EngagementsPage } from '../src/pages/EngagementsPage'
import { EventsPage } from '../src/pages/EventsPage'
import { NewEngagementPage } from '../src/pages/NewEngagementPage'
import { RaiseMisstatementPage } from '../src/pages/RaiseMisstatementPage'
import { SpinePage } from '../src/pages/SpinePage'
import { ThresholdsPage } from '../src/pages/ThresholdsPage'
import {
  createdPinned,
  createdUnlinked,
  createRefusals,
  eventsAnswers,
  eventsEvaluation,
  eventsPartner,
  eventsThresholds,
  misstatementRaised,
  misstatementRaisedNewLedger,
  raiseRefusals,
  refuse,
  spineAnswers,
  spineClean,
  spineCleanEmpty,
  spineLinkRefusals,
  spineLinkSet,
  spineProblems,
  spineUnlinked,
  spineUnreachable,
  thresholdRefusals,
  thresholdRevised,
  thresholdSet,
  thresholdsAnswers,
  thresholdsNone,
  thresholdsOne,
  thresholdsSpineDown,
  thresholdsTwo,
  type SpineScreen,
  type ThresholdsScreen,
} from './closureFixtures'
import notFound from './fixtures/engagement-not-found.json'
import { answered, deferred, failApi, inTurn, mockApi, refusal, requested, sent } from './mockApi'

afterEach(() => {
  vi.unstubAllGlobals()
  window.location.hash = ''
})

function panel(name: string | RegExp): HTMLElement {
  return screen.getByRole('region', { name })
}

function fact(panelName: string | RegExp, label: string): HTMLElement {
  const term = within(panel(panelName)).getByText(label, { selector: 'dt' })
  const value = term.nextElementSibling
  if (!(value instanceof HTMLElement)) throw new Error(`${label} has no value`)
  return value
}

function type(label: string | RegExp, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } })
}

function posts(): string[] {
  return requested().filter((request) => request.startsWith('POST'))
}

/** The answers before a write and, for each read, the answers after it. */
function inTurns(before: Record<string, unknown>, after: Record<string, unknown>) {
  return Object.fromEntries(
    Object.keys(before).map((key) => [key, inTurn(before[key], after[key])]),
  )
}

// =====================================================================================
// Creating an engagement
// =====================================================================================

test('the engagement list offers a way to create one', async () => {
  mockApi({ 'GET /api/engagements': [] })
  render(<EngagementsPage />)
  expect(await screen.findByText('No engagements yet')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'New engagement' })).toHaveAttribute(
    'href',
    '#/engagements/new',
  )
})

test('an engagement needs a name before it can be created', () => {
  mockApi({})
  render(<NewEngagementPage />)
  const create = screen.getByRole('button', { name: 'Create engagement' })
  expect(screen.getByLabelText(/^Name/)).toBeRequired()
  expect(create).toBeDisabled()
  type(/^Name/, '   ')
  expect(create).toBeDisabled()
  fireEvent.submit(screen.getByRole('form', { name: 'New engagement' }))
  expect(posts()).toEqual([])
  type(/^Name/, 'FY26 audit')
  expect(create).toBeEnabled()
})

test('creating an unlinked engagement sends its name and opens its schedule', async () => {
  mockApi({ 'POST /api/engagements': answered(201, createdUnlinked) })
  render(<NewEngagementPage />)
  type(/^Name/, `  ${createdUnlinked.label}  `)
  fireEvent.click(screen.getByRole('button', { name: 'Create engagement' }))
  await vi.waitFor(() => {
    expect(window.location.hash).toBe(`#/engagements/${createdUnlinked.id}`)
  })
  expect(sent()).toEqual([
    {
      request: 'POST /api/engagements',
      body: { label: createdUnlinked.label, spine_engagement_id: null, spine_version_id: null },
      contentType: 'application/json',
    },
  ])
})

test('creating a linked engagement sends the Spine engagement and version', async () => {
  mockApi({ 'POST /api/engagements': answered(201, createdPinned) })
  render(<NewEngagementPage />)
  type(/^Name/, createdPinned.label)
  type(/^Financial Spine engagement/, createdPinned.spine.engagement_id ?? '')
  type(/^Financial Spine version/, createdPinned.spine.version_id ?? '')
  fireEvent.click(screen.getByRole('button', { name: 'Create engagement' }))
  await vi.waitFor(() => {
    expect(window.location.hash).toBe(`#/engagements/${createdPinned.id}`)
  })
  expect(sent().map((entry) => entry.body)).toEqual([
    {
      label: createdPinned.label,
      spine_engagement_id: createdPinned.spine.engagement_id,
      spine_version_id: createdPinned.spine.version_id,
    },
  ])
})

test('a refused engagement is explained in the backend’s words, and nothing is opened', async () => {
  for (const [captured, words] of [
    [createRefusals.unknownSpineEngagement, 'No engagement 99999999-9999-4999-8999-999999999999'],
    [
      createRefusals.versionWithoutEngagement,
      'Value error, a Spine version needs the Spine engagement it belongs to',
    ],
    [createRefusals.blankLabel, 'label: String should have at least 1 character'],
  ] as const) {
    mockApi({ 'POST /api/engagements': refuse(captured) })
    const view = render(<NewEngagementPage />)
    type(/^Name/, 'Test engagement')
    fireEvent.click(screen.getByRole('button', { name: 'Create engagement' }))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('The engagement was not created')
    expect(alert).toHaveTextContent(words)
    expect(alert).toHaveTextContent(`/api/engagements answered ${String(captured.status)}`)
    expect(window.location.hash).toBe('')
    // What was typed is kept.
    expect(screen.getByLabelText(/^Name/)).toHaveValue('Test engagement')
    view.unmount()
    vi.unstubAllGlobals()
  }
})

test('an engagement is created once, however many times the form is sent', async () => {
  const pending = deferred()
  mockApi({ 'POST /api/engagements': pending.answer })
  render(<NewEngagementPage />)
  type(/^Name/, 'FY26 audit')
  const create = screen.getByRole('button', { name: 'Create engagement' })
  fireEvent.click(create)
  fireEvent.click(create)
  fireEvent.submit(screen.getByRole('form', { name: 'New engagement' }))
  expect(posts()).toHaveLength(1)
  expect(screen.getByRole('button', { name: 'Creating…' })).toBeDisabled()
  expect(screen.getByLabelText(/^Name/)).toBeDisabled()
  await act(async () => {
    pending.arrive(answered(201, createdUnlinked))
    await pending.answer
  })
  await vi.waitFor(() => {
    expect(window.location.hash).toBe(`#/engagements/${createdUnlinked.id}`)
  })
  expect(posts()).toHaveLength(1)
})

// =====================================================================================
// Thresholds
// =====================================================================================

async function openThresholds(snapshot: ThresholdsScreen, answers: Record<string, unknown> = {}) {
  mockApi({ ...thresholdsAnswers(snapshot), ...answers })
  const view = render(<ThresholdsPage id={snapshot.engagement.id} />)
  await screen.findByRole('heading', { level: 1 })
  return view
}

function thresholdsPath(snapshot: ThresholdsScreen): string {
  return `POST /api/engagements/${snapshot.engagement.id}/thresholds`
}

function fillThresholds(values: { om: string; pm: string; fraction: string; basis: string }) {
  type(/^Overall materiality/, values.om)
  type(/^Performance materiality/, values.pm)
  type(/^Clearly-trivial fraction of PM/, values.fraction)
  type(/^Basis/, values.basis)
}

test('the thresholds screen says it is loading, then reads the four things it needs', async () => {
  const id = thresholdsOne.engagement.id
  mockApi(thresholdsAnswers(thresholdsOne))
  render(<ThresholdsPage id={id} />)
  expect(screen.getByRole('status')).toHaveTextContent('Loading the thresholds…')
  await screen.findByRole('heading', { level: 1, name: thresholdsOne.engagement.label })
  expect(requested().sort()).toEqual(
    [
      `GET /api/engagements/${id}`,
      `GET /api/engagements/${id}/thresholds`,
      `GET /api/engagements/${id}/thresholds/history`,
      `GET /api/engagements/${id}/events`,
    ].sort(),
  )
})

test('with no thresholds the screen says so in the backend’s words and offers to set them', async () => {
  await openThresholds(thresholdsNone)
  expect(thresholdsNone.current.current).toBeNull()
  expect(screen.getByText('no thresholds have been set for this engagement')).toBeInTheDocument()
  expect(screen.getByRole('form', { name: 'Set the thresholds' })).toBeInTheDocument()
  expect(screen.queryByRole('table', { name: 'Every version of the thresholds' })).toBeNull()
  expect(panel('Recomputes recorded')).toHaveTextContent('No recompute has been recorded')
  expect(screen.queryByText(/₹/)).not.toBeInTheDocument()
})

test('the current thresholds show the three lines, the fraction, the basis, and who set them and when', async () => {
  await openThresholds(thresholdsOne)
  const current = thresholdsOne.current.current
  if (current === null) throw new Error('the fixture has no thresholds')
  const name = 'Current thresholds: version 1'
  expect(fact(name, 'Overall materiality (OM)')).toHaveTextContent(/^₹4,00,000.00$/)
  expect(fact(name, 'Performance materiality (PM)')).toHaveTextContent(/^₹2,50,000.00$/)
  // The clearly-trivial amount is the backend's: PM times the declared fraction.
  expect(fact(name, 'Clearly trivial (CTT)')).toHaveTextContent(/^₹12,500.00$/)
  expect(fact(name, 'Declared fraction of PM')).toHaveTextContent(/^0.05$/)
  expect(fact(name, 'Basis')).toHaveTextContent(/^C-1$/)
  expect(fact(name, 'Set by')).toHaveTextContent(/^senior@firm$/)
  expect(fact(name, 'Set')).toHaveTextContent(dateTime(current.set_at))
  expect(fact(name, 'PM below OM')).toHaveTextContent(/^Yes$/)
  expect(within(panel(name)).getByText(current.checks.note)).toBeInTheDocument()
})

test('the check against the Spine’s performance materiality is shown as the backend reports it', async () => {
  await openThresholds(thresholdsOne)
  const name = 'Current thresholds: version 1'
  expect(thresholdsOne.current.current?.spine_pm_check?.status).toBe('match')
  expect(within(panel(name)).getByText('Matches the Spine')).toBeInTheDocument()
  expect(fact(name, 'PM held here')).toHaveTextContent(/^₹2,50,000.00$/)
  expect(fact(name, 'PM in the Spine now')).toHaveTextContent(/^₹2,50,000.00$/)
  expect(fact(name, 'PM in the Spine when set')).toHaveTextContent(/^₹2,50,000.00$/)
  expect(fact(name, 'Spine version')).toHaveTextContent(
    `Set against ${thresholdsOne.engagement.spine.version_id ?? ''}`,
  )
})

test('a PM that differs from the Spine’s is reported, never resolved', async () => {
  await openThresholds(thresholdsTwo)
  const name = 'Current thresholds: version 2'
  const check = thresholdsTwo.current.current?.spine_pm_check
  expect(check?.status).toBe('mismatch')
  expect(within(panel(name)).getByText('Differs from the Spine')).toBeInTheDocument()
  expect(within(panel(name)).getByText(check?.detail ?? 'missing')).toBeInTheDocument()
  expect(check?.detail).toContain('pending B4')
  expect(fact(name, 'PM held here')).toHaveTextContent(/^₹3,00,000.00$/)
  expect(fact(name, 'PM in the Spine now')).toHaveTextContent(/^₹2,50,000.00$/)
})

test('a Spine that cannot be reached leaves the check unknown, with the backend’s reason', async () => {
  await openThresholds(thresholdsSpineDown)
  const name = 'Current thresholds: version 2'
  expect(within(panel(name)).getByText('Spine unreachable')).toBeInTheDocument()
  expect(
    within(panel(name)).getByText('the Financial Spine cannot be reached for a version'),
  ).toBeInTheDocument()
  expect(fact(name, 'PM in the Spine now')).toHaveTextContent(/^—$/)
  // The thresholds themselves are held here and are still shown.
  expect(fact(name, 'Overall materiality (OM)')).toHaveTextContent(/^₹5,00,000.00$/)
})

test('every version is listed, with the current one marked and the earlier one kept', async () => {
  await openThresholds(thresholdsTwo)
  const table = screen.getByRole('table', { name: 'Every version of the thresholds' })
  const rows = within(table)
    .getAllByRole('row')
    .slice(1)
    .map((row) => [...row.children].map((cell) => cell.textContent))
  const [second, first] = thresholdsTwo.history
  expect(rows).toEqual([
    [
      'Version 2',
      '₹5,00,000.00',
      '₹3,00,000.00',
      '₹12,000.00',
      '0.04',
      'C-1 revised: benchmark updated to final profit before tax',
      `${dateTime(second?.set_at)}by manager@firm`,
      'Current',
    ],
    [
      'Version 1',
      '₹4,00,000.00',
      '₹2,50,000.00',
      '₹12,500.00',
      '0.05',
      'C-1',
      `${dateTime(first?.set_at)}by senior@firm`,
      'Superseded',
    ],
  ])
})

test('each recompute is shown as the backend recorded it: what changed, by whom, and that bands recompute', async () => {
  await openThresholds(thresholdsTwo)
  const recompute = thresholdsTwo.events.find((event) => event.kind === 'threshold_recompute')
  if (recompute === undefined) throw new Error('the fixture has no recompute event')
  const entries = within(
    within(panel('Recomputes recorded')).getByRole('list', { name: 'Recomputes recorded' }),
  ).getAllByRole('listitem')
  const entry = entries[0]
  expect(entry).toHaveTextContent('Version 1 to version 2')
  expect(entry).toHaveTextContent(`by manager@firm, ${dateTime(recompute.at)}`)
  expect(entry).toHaveTextContent('Overall materiality: ₹4,00,000.00 to ₹5,00,000.00')
  expect(entry).toHaveTextContent('Performance materiality: ₹2,50,000.00 to ₹3,00,000.00')
  expect(entry).toHaveTextContent('Clearly trivial: ₹12,500.00 to ₹12,000.00')
  expect(entry).toHaveTextContent('Fraction of PM: 0.05 to 0.04')
  expect(entry).toHaveTextContent(String(recompute.payload.bands))
})

test('thresholds cannot be sent until every figure and the basis are given', async () => {
  await openThresholds(thresholdsNone)
  const set = screen.getByRole('button', { name: 'Set thresholds' })
  expect(set).toBeDisabled()
  fillThresholds({ om: '400000.00', pm: '250000.00', fraction: '0.05', basis: '' })
  expect(set).toBeDisabled()
  fillThresholds({ om: '4,00,000', pm: '250000.00', fraction: '0.05', basis: 'C-1' })
  expect(set).toBeDisabled() // an amount is digits and at most two decimals
  fireEvent.submit(screen.getByRole('form', { name: 'Set the thresholds' }))
  expect(posts()).toEqual([])
  fillThresholds({ om: '400000.00', pm: '250000.00', fraction: '0.05', basis: 'C-1' })
  expect(set).toBeEnabled()
})

test('setting thresholds sends the figures as typed, exactly, and reads the screen again', async () => {
  await openThresholds(thresholdsNone, {
    ...inTurns(thresholdsAnswers(thresholdsNone), thresholdsAnswers(thresholdsOne)),
    [thresholdsPath(thresholdsNone)]: answered(201, thresholdSet),
  })
  fillThresholds({ om: ' 400000.00 ', pm: '250000.00', fraction: '0.05', basis: ' C-1 ' })
  fireEvent.click(screen.getByRole('button', { name: 'Set thresholds' }))
  expect(
    await screen.findByText('Recorded: thresholds version 1, clearly trivial ₹12,500.00.'),
  ).toBeInTheDocument()
  // Strings, not numbers: nothing is rounded or re-formatted on the way out.
  expect(sent()).toEqual([
    {
      request: `POST /api/engagements/${thresholdsNone.engagement.id}/thresholds`,
      body: { om: '400000.00', pm: '250000.00', ctt_fraction: '0.05', basis: 'C-1' },
      contentType: 'application/json',
    },
  ])
  expect(await screen.findByRole('region', { name: 'Current thresholds: version 1' })).toBeVisible()
  expect(screen.getByRole('form', { name: 'Revise the thresholds' })).toBeInTheDocument()
  expect(screen.getByLabelText(/^Overall materiality/)).toHaveValue('')
})

test('revising thresholds adds a version and says the recompute is recorded', async () => {
  await openThresholds(thresholdsOne, {
    ...inTurns(thresholdsAnswers(thresholdsOne), thresholdsAnswers(thresholdsTwo)),
    [thresholdsPath(thresholdsOne)]: answered(201, thresholdRevised),
  })
  expect(panel('Revise the thresholds')).toHaveTextContent(
    'Revising the thresholds is how a reassessment of materiality is recorded.',
  )
  fillThresholds({
    om: '500000.00',
    pm: '300000.00',
    fraction: '0.04',
    basis: 'C-1 revised: benchmark updated to final profit before tax',
  })
  fireEvent.click(screen.getByRole('button', { name: 'Revise thresholds' }))
  expect(
    await screen.findByText(
      'Recorded: thresholds version 2, clearly trivial ₹12,000.00. The recompute of every band is recorded.',
    ),
  ).toBeInTheDocument()
  expect(thresholdRevised.recompute_event?.kind).toBe('threshold_recompute')
  expect(await screen.findByRole('region', { name: 'Current thresholds: version 2' })).toBeVisible()
  // The earlier version is kept, as superseded.
  expect(
    within(screen.getByRole('row', { name: /^Version 1 / })).getByText('Superseded'),
  ).toBeVisible()
})

test('thresholds the backend refuses are explained in its words', async () => {
  for (const [captured, words] of [
    [
      thresholdRefusals.pmNotBelowOm,
      'performance materiality (400000.00) must be below overall materiality (400000.00): SA 320 paragraph 9',
    ],
    [thresholdRefusals.fractionTooLarge, 'ctt_fraction: Input should be less than 1'],
    [thresholdRefusals.noFraction, 'ctt_fraction: Field required; basis: Field required'],
  ] as const) {
    const view = await openThresholds(thresholdsNone, {
      [thresholdsPath(thresholdsNone)]: refuse(captured),
    })
    fillThresholds({ om: '400000.00', pm: '400000.00', fraction: '1.5', basis: 'C-1' })
    fireEvent.click(screen.getByRole('button', { name: 'Set thresholds' }))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('The thresholds were not set')
    expect(alert).toHaveTextContent(words)
    expect(alert).toHaveTextContent(`answered ${String(captured.status)}`)
    // What was typed is kept, and nothing was read again.
    expect(screen.getByLabelText(/^Performance materiality/)).toHaveValue('400000.00')
    expect(requested().filter((request) => request.startsWith('GET'))).toHaveLength(4)
    view.unmount()
    vi.unstubAllGlobals()
  }
})

test('thresholds go out once while they are being recorded', async () => {
  const pending = deferred()
  await openThresholds(thresholdsNone, { [thresholdsPath(thresholdsNone)]: pending.answer })
  fillThresholds({ om: '400000.00', pm: '250000.00', fraction: '0.05', basis: 'C-1' })
  const set = screen.getByRole('button', { name: 'Set thresholds' })
  fireEvent.click(set)
  fireEvent.click(set)
  fireEvent.submit(screen.getByRole('form', { name: 'Set the thresholds' }))
  expect(posts()).toHaveLength(1)
  expect(screen.getByRole('button', { name: 'Recording…' })).toBeDisabled()
  await act(async () => {
    pending.arrive(answered(201, thresholdSet))
    await pending.answer
  })
  await screen.findByText(/^Recorded: thresholds version 1/)
  expect(posts()).toHaveLength(1)
})

test('an engagement that does not exist is refused on the thresholds screen', async () => {
  const id = '00000000-0000-4000-8000-000000000000'
  mockApi({ [`GET /api/engagements/${id}`]: refusal(404, notFound) })
  render(<ThresholdsPage id={id} />)
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent('The thresholds could not be loaded')
  expect(alert).toHaveTextContent(notFound.detail)
})

test('an unreachable backend is explained on the thresholds screen, and trying again loads it', async () => {
  failApi()
  render(<ThresholdsPage id={thresholdsOne.engagement.id} />)
  expect(await screen.findByRole('alert')).toHaveTextContent('The backend could not be reached.')
  mockApi(thresholdsAnswers(thresholdsOne))
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
  expect(await screen.findByRole('heading', { level: 1 })).toBeInTheDocument()
})

// =====================================================================================
// The Financial Spine: the link and the reconciliation
// =====================================================================================

async function openSpine(snapshot: SpineScreen, answers: Record<string, unknown> = {}) {
  mockApi({ ...spineAnswers(snapshot), ...answers })
  const view = render(<SpinePage id={snapshot.engagement.id} />)
  await screen.findByRole('heading', { level: 1 })
  return view
}

function linkPath(snapshot: SpineScreen): string {
  return `POST /api/engagements/${snapshot.engagement.id}/spine-link`
}

test('an unlinked engagement says so, and its reconciliation is not available, for the backend’s reason', async () => {
  await openSpine(spineUnlinked)
  expect(
    within(panel('Link to the Financial Spine')).getByText('Not linked to the Financial Spine'),
  ).toBeInTheDocument()
  const report = panel('Reconciliation with the Financial Spine')
  expect(within(report).getByText('No Spine version pinned')).toBeInTheDocument()
  expect(report).toHaveTextContent('The reconciliation is not available.')
  expect(report).toHaveTextContent('no Spine version is pinned')
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
})

test('a linked engagement shows its Spine engagement and version, verified', async () => {
  await openSpine(spineCleanEmpty)
  const { spine } = spineCleanEmpty.engagement
  expect(
    within(panel('Link to the Financial Spine')).getByText('Financial Spine link verified'),
  ).toBeInTheDocument()
  expect(fact('Link to the Financial Spine', 'Spine engagement')).toHaveTextContent(
    spine.engagement_id ?? 'missing',
  )
  expect(fact('Link to the Financial Spine', 'Spine version')).toHaveTextContent(
    spine.version_id ?? 'missing',
  )
  // The form starts from the link as it is.
  expect(screen.getByLabelText(/^Financial Spine engagement/)).toHaveValue(spine.engagement_id)
  expect(screen.getByLabelText(/^Financial Spine version/)).toHaveValue(spine.version_id)
})

test('setting the link sends both identifiers and reads the screen again', async () => {
  const linked: SpineScreen = { ...spineCleanEmpty, engagement: spineLinkSet }
  const id = spineUnlinked.engagement.id
  expect(spineLinkSet.id).toBe(id)
  await openSpine(spineUnlinked, {
    [`GET /api/engagements/${id}`]: inTurn(spineUnlinked.engagement, spineLinkSet),
    [`GET /api/engagements/${id}/spine-reconciliation`]: inTurn(
      spineUnlinked.reconciliation,
      linked.reconciliation,
    ),
    [linkPath(spineUnlinked)]: answered(200, spineLinkSet),
  })
  type(/^Financial Spine engagement/, spineLinkSet.spine.engagement_id ?? '')
  type(/^Financial Spine version/, spineLinkSet.spine.version_id ?? '')
  fireEvent.click(screen.getByRole('button', { name: 'Save the link' }))
  expect(await screen.findByText('Recorded: the Financial Spine link.')).toBeInTheDocument()
  expect(sent().map((entry) => entry.body)).toEqual([
    {
      spine_engagement_id: spineLinkSet.spine.engagement_id,
      spine_version_id: spineLinkSet.spine.version_id,
    },
  ])
  expect(await screen.findByText('Financial Spine link verified')).toBeInTheDocument()
})

test('clearing the link sends nulls, never empty text', async () => {
  await openSpine(spineCleanEmpty, {
    [linkPath(spineCleanEmpty)]: answered(200, spineUnlinked.engagement),
  })
  type(/^Financial Spine engagement/, '')
  type(/^Financial Spine version/, '   ')
  fireEvent.click(screen.getByRole('button', { name: 'Save the link' }))
  await screen.findByText('Recorded: the Financial Spine link.')
  expect(sent().map((entry) => entry.body)).toEqual([
    { spine_engagement_id: null, spine_version_id: null },
  ])
})

test('a link the backend refuses is explained, with the pending decision it rests on', async () => {
  await openSpine(spineClean, { [linkPath(spineClean)]: refuse(spineLinkRefusals.afterRaising) })
  type(/^Financial Spine version/, '')
  fireEvent.click(screen.getByRole('button', { name: 'Save the link' }))
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent('The link was not changed')
  expect(alert).toHaveTextContent(
    'this engagement already has misstatements proposed on its pinned Spine version',
  )
  expect(alert).toHaveTextContent('answered 409 · pending decision B10')
  expect(screen.queryByText('Recorded: the Financial Spine link.')).not.toBeInTheDocument()
})

test('a Spine version that does not exist is refused in the backend’s words', async () => {
  await openSpine(spineUnlinked, {
    [linkPath(spineUnlinked)]: refuse(spineLinkRefusals.unknownVersion),
  })
  type(/^Financial Spine engagement/, '11111111-1111-4111-8111-111111111111')
  type(/^Financial Spine version/, '99999999-9999-4999-8999-999999999999')
  fireEvent.click(screen.getByRole('button', { name: 'Save the link' }))
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'No spine_version 99999999-9999-4999-8999-999999999999',
  )
})

test('a clean reconciliation says so and lists nothing', async () => {
  await openSpine(spineClean)
  const report = panel('Reconciliation with the Financial Spine')
  expect(spineClean.reconciliation.clean).toBe(true)
  expect(within(report).getByText('Clean')).toBeInTheDocument()
  expect(report).toHaveTextContent('0 orphans, 0 missing, 0 disagreements')
  expect(report).toHaveTextContent(
    'Adjustments in the Spine that belong to no misstatement of this module: 0.',
  )
  expect(within(report).getByText(spineClean.reconciliation.basis ?? 'missing')).toBeVisible()
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
})

test('every kind of finding is listed as the backend reports it', async () => {
  await openSpine(spineProblems)
  const report = panel('Reconciliation with the Financial Spine')
  const found = spineProblems.reconciliation
  expect(within(report).getByText('Findings')).toBeInTheDocument()
  expect(report).toHaveTextContent('1 orphan, 1 missing, 1 disagreement')

  // An orphan: the Spine holds a proposal that nothing here links to.
  const orphans = screen.getByRole('table', {
    name: 'Adjustments in the Financial Spine that no misstatement here links to',
  })
  const orphan = found.orphans?.[0]
  const row = within(orphans).getByRole('row', { name: /^M-3 / })
  expect(row).toHaveTextContent('Electricity for March not accrued')
  expect(row).toHaveTextContent('proposed (correction)')
  expect(row).toHaveTextContent('₹60,000.00')
  expect(row).toHaveTextContent(orphan?.adjustment_id ?? 'missing')
  expect(orphan?.measure).toBe('60000.00')

  // A misstatement whose adjustment the Spine no longer has.
  const missing = within(report).getByRole('list', { name: 'Missing adjustments' })
  expect(missing).toHaveTextContent('M-3, raised here: the Spine has no adjustment')
  expect(missing).toHaveTextContent(found.missing?.[0]?.spine_adjustment_id ?? 'missing')

  // A state the two modules disagree on.
  expect(within(report).getByRole('list', { name: 'Disagreements' })).toHaveTextContent(
    'M-1 is raised here, which expects the Spine’s adjustment to be proposed; the Spine holds it accepted.',
  )
  // Nothing on the screen repairs any of it.
  expect(within(report).queryByRole('button')).not.toBeInTheDocument()
})

test('a Spine that cannot be reached leaves the reconciliation unavailable, and says why', async () => {
  await openSpine(spineUnreachable)
  expect(
    within(panel('Link to the Financial Spine')).getByText('Financial Spine unreachable'),
  ).toBeInTheDocument()
  const report = panel('Reconciliation with the Financial Spine')
  expect(within(report).getByText('Spine unreachable')).toBeInTheDocument()
  expect(report).toHaveTextContent('the Financial Spine cannot be reached for the adjustments')
  expect(report).not.toHaveTextContent('Clean')
})

// =====================================================================================
// The event trail
// =====================================================================================

test('an engagement with no events says what would be recorded', async () => {
  mockApi(eventsAnswers({ engagement: thresholdsNone.engagement, events: [] }))
  render(<EventsPage id={thresholdsNone.engagement.id} />)
  expect(await screen.findByText('No events recorded')).toBeInTheDocument()
  expect(screen.queryByRole('list', { name: 'Events, oldest first' })).toBeNull()
})

test('each event shows what happened, who did it, when, and what was recorded', async () => {
  mockApi(eventsAnswers(eventsPartner))
  render(<EventsPage id={eventsPartner.engagement.id} />)
  const list = await screen.findByRole('list', { name: 'Events, oldest first' })
  const entries = within(list)
    .getAllByRole('listitem')
    .filter((entry) => entry.parentElement === list)
  expect(eventsPartner.events.map((event) => event.kind)).toEqual([
    'materiality_reassessed',
    'soft_gate_acknowledged',
    'materiality_reassessed',
    'evaluation_concluded',
  ])
  expect(entries).toHaveLength(4)
  expect(entries[0]).toHaveTextContent('Materiality reassessed before an evaluation')
  expect(entries[0]).toHaveTextContent('by senior@firm')
  expect(entries[1]).toHaveTextContent('Soft gate acknowledged by the partner')
  expect(entries[1]).toHaveTextContent('by partner@firm')
  expect(entries[1]).toHaveTextContent(dateTime(eventsPartner.events[1]?.at))
  expect(entries[3]).toHaveTextContent('Conclusion recorded')
  // The payload is shown as it was recorded, key by key.
  const acknowledged = eventsPartner.events[1]
  expect(entries[1]).toHaveTextContent('noteReviewed with the manager; see C-4')
  expect(entries[1]).toHaveTextContent(`pm${String(acknowledged?.payload.pm)}`)
  expect(screen.getByRole('region', { name: '4 events' })).toBeInTheDocument()
})

test('the trail shows a threshold revision and a strategy answer too', async () => {
  mockApi({ ...eventsAnswers(eventsThresholds), ...eventsAnswers(eventsEvaluation) })
  const view = render(<EventsPage id={eventsThresholds.engagement.id} />)
  expect(await screen.findByText('Thresholds revised: every band recomputes')).toBeVisible()
  view.rerender(<EventsPage id={eventsEvaluation.engagement.id} />)
  expect(await screen.findByText('Strategy prompt answered')).toBeVisible()
  expect(screen.getByRole('region', { name: '1 event' })).toBeInTheDocument()
})

test('an event kind this screen has no word for is shown as the backend named it', async () => {
  const [first] = eventsThresholds.events
  if (first === undefined) throw new Error('the fixture has no event')
  mockApi(
    eventsAnswers({
      engagement: eventsThresholds.engagement,
      events: [{ ...first, kind: 'a_kind_added_later' }],
    }),
  )
  render(<EventsPage id={eventsThresholds.engagement.id} />)
  const list = await screen.findByRole('list', { name: 'Events, oldest first' })
  expect(within(list).getAllByText('a_kind_added_later').length).toBeGreaterThan(0)
})

// =====================================================================================
// Recording a misstatement
// =====================================================================================

const pinned = createdPinned
const raisePath = `POST /api/engagements/${pinned.id}/misstatements`

async function openRaise(answers: Record<string, unknown> = {}, engagement = pinned) {
  mockApi({ [`GET /api/engagements/${engagement.id}`]: engagement, ...answers })
  const view = render(<RaiseMisstatementPage id={engagement.id} />)
  await screen.findByRole('heading', { level: 1, name: 'Record a misstatement' })
  return view
}

function fillRent() {
  type(/^Description/, 'Rent for March not accrued')
  type(/^Working paper reference/, 'E-4.2')
  type('Line 1 import line number', '5')
  type('Line 1 amount', '60000.00')
  type('Line 2 import line number', '3')
  type('Line 2 amount', '60000.00')
}

const record = () => screen.getByRole('button', { name: 'Record misstatement' })

test('the recording form starts with two lines, a debit and a credit', async () => {
  await openRaise()
  expect(screen.getAllByRole('group', { name: /^Line \d+$/ })).toHaveLength(2)
  expect(screen.getByLabelText('Line 1 side')).toHaveValue('dr')
  expect(screen.getByLabelText('Line 2 side')).toHaveValue('cr')
  // Two lines is the least a double entry can have, so neither can be removed.
  expect(screen.queryByRole('button', { name: /^Remove line/ })).not.toBeInTheDocument()
  expect(record()).toBeDisabled()
})

test('a misstatement cannot be sent until its description, working paper and lines are given', async () => {
  await openRaise()
  type(/^Description/, 'Rent for March not accrued')
  type('Line 1 import line number', '5')
  type('Line 1 amount', '60000.00')
  type('Line 2 import line number', '3')
  type('Line 2 amount', '60000.00')
  expect(record()).toBeDisabled() // no working paper reference: the spec requires one
  type(/^Working paper reference/, 'E-4.2')
  expect(record()).toBeEnabled()
  type('Line 2 amount', 'sixty thousand')
  expect(record()).toBeDisabled()
  fireEvent.submit(screen.getByRole('form', { name: 'Record a misstatement' }))
  expect(posts()).toEqual([])
})

test('recording sends the lines as typed, exactly, and opens the misstatement', async () => {
  await openRaise({ [raisePath]: answered(201, misstatementRaised) })
  fillRent()
  fireEvent.click(record())
  await vi.waitFor(() => {
    expect(window.location.hash).toBe(`#/misstatements/${misstatementRaised.id}`)
  })
  // The amounts are the text that was typed: strings, never numbers.
  expect(sent()).toEqual([
    {
      request: `POST /api/engagements/${pinned.id}/misstatements`,
      body: {
        type: 'factual',
        description: 'Rent for March not accrued',
        raised_from: 'wp',
        source_ref: 'E-4.2',
        lines: [
          { line_no: 5, dr: '60000.00' },
          { line_no: 3, cr: '60000.00' },
        ],
      },
      contentType: 'application/json',
    },
  ])
  // What came back is what the backend recorded and the Spine holds.
  expect(
    misstatementRaised.spine.lines.map((line) => [line.ledger_name, line.dr, line.cr]),
  ).toEqual([
    ['Rent', '60000.00', '0.00'],
    ['Provision for expenses', '0.00', '60000.00'],
  ])
})

test('a judgemental misstatement carries its range, and a ledger the import lacks is named', async () => {
  await openRaise({ [raisePath]: answered(201, misstatementRaisedNewLedger) })
  fireEvent.change(screen.getByLabelText(/^Type/), { target: { value: 'judgemental' } })
  fireEvent.change(screen.getByLabelText(/^Raised from/), { target: { value: 'manual' } })
  type(/^Description/, 'Provision for doubtful debts understated')
  type(/^Working paper reference/, 'R-7.1')
  expect(record()).toBeDisabled()
  type(/^Auditor’s range: low/, '20000.00')
  type(/^Auditor’s range: high/, '40000.00')
  fireEvent.change(screen.getByLabelText('Line 1 ledger'), { target: { value: 'new' } })
  type('Line 1 ledger name', 'Bad debts')
  type('Line 1 groups', 'Indirect Expenses')
  type('Line 1 Schedule III head', 'pl.expenses.other')
  type('Line 1 amount', '30000.00')
  type('Line 2 import line number', '1')
  type('Line 2 amount', '30000.00')
  fireEvent.click(record())
  await vi.waitFor(() => {
    expect(window.location.hash).toBe(`#/misstatements/${misstatementRaisedNewLedger.id}`)
  })
  expect(sent().map((entry) => entry.body)).toEqual([
    {
      type: 'judgemental',
      description: 'Provision for doubtful debts understated',
      raised_from: 'manual',
      source_ref: 'R-7.1',
      range_low: '20000.00',
      range_high: '40000.00',
      lines: [
        {
          ledger_name: 'Bad debts',
          parent_chain: ['Indirect Expenses'],
          head_id: 'pl.expenses.other',
          dr: '30000.00',
        },
        { line_no: 1, cr: '30000.00' },
      ],
    },
  ])
})

test('a projected misstatement must name its sample and projection basis', async () => {
  await openRaise({ [raisePath]: answered(201, misstatementRaised) })
  fillRent()
  fireEvent.change(screen.getByLabelText(/^Type/), { target: { value: 'projected' } })
  expect(record()).toBeDisabled()
  type(/^Sample \(/, 'S-12')
  expect(record()).toBeDisabled()
  type(/^Projection basis/, 'Ratio of error to sample value')
  // Since Pass 2 (D65) it says how it was projected too.
  expect(record()).toBeDisabled()
  type(/^Population value/, '4000000.00')
  type(/^Items in the population/, '1200')
  type(/^Sample value/, '400000.00')
  type(/^Items in the sample/, '120')
  type(/^Misstatement found in the sample/, '4000.00')
  type(/^Projected amount/, '60000.00')
  expect(record()).toBeEnabled()
  fireEvent.click(record())
  await vi.waitFor(() => {
    expect(posts()).toHaveLength(1)
  })
  expect(sent()[0]?.body).toMatchObject({
    type: 'projected',
    sample_ref: 'S-12',
    projection_basis: 'Ratio of error to sample value',
    sampling_method: 'ratio',
    population_value: '4000000.00',
    population_size: 1200,
    sample_value: '400000.00',
    sample_size: 120,
    known_error_in_sample: '4000.00',
    projected_amount: '60000.00',
  })
  // A range belongs to a judgemental misstatement only.
  expect(sent()[0]?.body).not.toHaveProperty('range_low')
})

test('lines can be added and removed, and groups are split outermost first', async () => {
  await openRaise({ [raisePath]: answered(201, misstatementRaised) })
  fillRent()
  fireEvent.click(screen.getByRole('button', { name: 'Add a line' }))
  expect(screen.getAllByRole('group', { name: /^Line \d+$/ })).toHaveLength(3)
  expect(record()).toBeDisabled() // the new line is empty
  fireEvent.change(screen.getByLabelText('Line 3 ledger'), { target: { value: 'new' } })
  type('Line 3 ledger name', 'Rent deposit')
  type('Line 3 groups', ' Current Assets > Loans and Advances ')
  type('Line 3 Schedule III head', 'bs.assets.current.cash')
  type('Line 3 amount', '1.5')
  fireEvent.click(record())
  await vi.waitFor(() => {
    expect(posts()).toHaveLength(1)
  })
  expect((sent()[0]?.body as { lines: unknown[] }).lines[2]).toEqual({
    ledger_name: 'Rent deposit',
    parent_chain: ['Current Assets', 'Loans and Advances'],
    head_id: 'bs.assets.current.cash',
    dr: '1.5',
  })
})

test('a third line can be removed again, never the second', async () => {
  await openRaise()
  fireEvent.click(screen.getByRole('button', { name: 'Add a line' }))
  fireEvent.click(screen.getByRole('button', { name: 'Remove line 3' }))
  expect(screen.getAllByRole('group', { name: /^Line \d+$/ })).toHaveLength(2)
  expect(screen.queryByRole('button', { name: /^Remove line/ })).not.toBeInTheDocument()
})

test('every refusal of the backend is shown in its words, and nothing typed is lost', async () => {
  for (const [captured, words] of [
    [
      raiseRefusals.unbalanced,
      'the Dr/Cr lines must balance: debits 60000.00 differ from credits 50000.00 (spec section 3.1; acceptance 1)',
    ],
    [raiseRefusals.oneLine, 'lines: List should have at least 2 items after validation, not 1'],
    [raiseRefusals.unknownLine, 'line_no 999 is not a ledger of the pinned Spine version'],
    [
      raiseRefusals.judgementalWithoutRange,
      'a judgemental misstatement carries range_low and range_high',
    ],
    [
      raiseRefusals.projectedWithoutSample,
      'a projected misstatement names its sample_ref and projection_basis',
    ],
    [
      raiseRefusals.onUnlinkedEngagement,
      'no Financial Spine version is pinned to this engagement; set the Spine link first',
    ],
    [raiseRefusals.commitFailed, 'the database refused the commit'],
  ] as const) {
    const view = await openRaise({ [raisePath]: refuse(captured) })
    fillRent()
    fireEvent.click(record())
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('The misstatement was not recorded')
    expect(alert).toHaveTextContent(words)
    expect(alert).toHaveTextContent(`answered ${String(captured.status)}`)
    expect(window.location.hash).toBe('')
    expect(screen.getByLabelText('Line 1 amount')).toHaveValue('60000.00')
    expect(record()).toBeEnabled()
    view.unmount()
    vi.unstubAllGlobals()
  }
})

test('an engagement with no pinned Spine version is warned about before anything is typed', async () => {
  await openRaise({}, createdUnlinked)
  expect(
    screen.getByText(/No Financial Spine version is pinned to this engagement\./),
  ).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Financial Spine' })).toHaveAttribute(
    'href',
    `#/engagements/${createdUnlinked.id}/spine`,
  )
})

test('a misstatement is recorded once while it is processing', async () => {
  const pending = deferred()
  await openRaise({ [raisePath]: pending.answer })
  fillRent()
  fireEvent.click(record())
  fireEvent.submit(screen.getByRole('form', { name: 'Record a misstatement' }))
  fireEvent.submit(screen.getByRole('form', { name: 'Record a misstatement' }))
  expect(posts()).toHaveLength(1)
  expect(screen.getByRole('button', { name: 'Recording…' })).toBeDisabled()
  expect(screen.getByLabelText('Line 1 amount')).toBeDisabled()
  await act(async () => {
    pending.arrive(answered(201, misstatementRaised))
    await pending.answer
  })
  await vi.waitFor(() => {
    expect(window.location.hash).toBe(`#/misstatements/${misstatementRaised.id}`)
  })
  expect(posts()).toHaveLength(1)
})

test('cancelling leads back to the schedule without sending anything', async () => {
  await openRaise()
  expect(screen.getByRole('link', { name: 'Cancel' })).toHaveAttribute(
    'href',
    `#/engagements/${pinned.id}`,
  )
  expect(posts()).toEqual([])
})

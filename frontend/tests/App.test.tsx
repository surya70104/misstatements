import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import type { Engagement } from '../src/api'
import { App } from '../src/App'
import list from './fixtures/engagements.json'
import {
  detailPath,
  raised,
  toCommunicated,
  transitionPath,
  workflowEngagement,
  workflowScheduleCommunicated,
  workflowScheduleRaised,
} from './detailFixtures'
import { clearNoRun, evaluationAnswers } from './evaluationFixtures'
import { answered, failApi, mockApi, requested } from './mockApi'
import {
  engagement,
  misstatement,
  misstatements,
  SCHEDULE,
  scheduleAnswers,
} from './scheduleFixtures'

const engagements = list as Engagement[]
const HEALTH = { status: 'ok', module: 'misstatements-rollup', version: '0.1.0' }

afterEach(() => {
  vi.unstubAllGlobals()
  window.location.hash = ''
})

test('the shell renders its title and reports a healthy backend', async () => {
  mockApi({ 'GET /api/health': HEALTH, 'GET /api/engagements': engagements })
  render(<App />)
  expect(screen.getByRole('link', { name: 'Misstatements Rollup' })).toBeInTheDocument()
  expect(screen.getByText('SA 450 · OAK Audit')).toBeInTheDocument()
  expect(await screen.findByText('Backend misstatements-rollup 0.1.0 is ok.')).toBeInTheDocument()
})

test('the shell says when the backend cannot be reached', async () => {
  failApi()
  render(<App />)
  expect(await screen.findByText('Backend unreachable: start it on port 8003.')).toBeInTheDocument()
})

test('a non-OK health answer counts as unreachable', async () => {
  mockApi({})
  render(<App />)
  expect(await screen.findByText('Backend unreachable: start it on port 8003.')).toBeInTheDocument()
})

test('the landing page is the engagement list, marked as the current page', async () => {
  mockApi({ 'GET /api/health': HEALTH, 'GET /api/engagements': engagements })
  render(<App />)
  expect(await screen.findByRole('heading', { name: 'Engagements' })).toBeInTheDocument()
  const nav = screen.getByRole('navigation', { name: 'Main' })
  expect(within(nav).getByRole('link', { name: 'Engagements' })).toHaveAttribute(
    'aria-current',
    'page',
  )
  expect(screen.getByRole('banner')).toBeInTheDocument()
  expect(screen.getByRole('main')).toBeInTheDocument()
  expect(screen.getByRole('contentinfo')).toBeInTheDocument()
})

test('following an engagement opens its schedule page, and the title leads back', async () => {
  mockApi({ 'GET /api/health': HEALTH, 'GET /api/engagements': engagements, ...SCHEDULE })
  render(<App />)
  const listed = engagements[0]
  if (listed === undefined) throw new Error('the engagements fixture is empty')
  const link = await screen.findByRole('link', { name: listed.label })
  expect(link).toHaveAttribute('href', `#/engagements/${listed.id}`)

  // jsdom does not follow a link's href by itself: go to an engagement's address, the one
  // whose schedule the fixtures hold.
  act(() => {
    window.location.hash = `#/engagements/${engagement.id}`
  })
  expect(await screen.findByRole('heading', { name: engagement.label })).toBeInTheDocument()
  expect(screen.getByRole('table', { name: 'Schedule of misstatements' })).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Engagements' })).not.toBeInTheDocument()
  const nav = screen.getByRole('navigation', { name: 'Main' })
  expect(within(nav).getByRole('link', { name: 'Engagements' })).not.toHaveAttribute('aria-current')
  expect(requested()).toContain(`GET /api/engagements/${engagement.id}`)

  const home = screen.getByRole('link', { name: 'Misstatements Rollup' })
  expect(home).toHaveAttribute('href', '#/')
  fireEvent.click(home)
  act(() => {
    window.location.hash = '#/'
  })
  expect(await screen.findByRole('heading', { name: 'Engagements' })).toBeInTheDocument()
})

test('a reference on the schedule opens that misstatement, which leads back to the schedule', async () => {
  window.location.hash = `#/engagements/${engagement.id}`
  mockApi({
    'GET /api/health': HEALTH,
    ...SCHEDULE,
    [`GET /api/misstatements/${misstatement.id}`]: misstatement,
  })
  render(<App />)
  const reference = await screen.findByRole('link', { name: misstatement.ref })
  expect(misstatements.map((entry) => entry.id)).toContain(misstatement.id)
  expect(reference).toHaveAttribute('href', `#/misstatements/${misstatement.id}`)

  act(() => {
    window.location.hash = reference.getAttribute('href') ?? ''
  })
  expect(await screen.findByRole('heading', { name: misstatement.ref })).toBeInTheDocument()
  expect(screen.getByRole('region', { name: 'Dr/Cr lines' })).toBeInTheDocument()
  expect(screen.queryByRole('table', { name: 'Schedule of misstatements' })).not.toBeInTheDocument()
  expect(requested()).toContain(`GET /api/misstatements/${misstatement.id}`)

  const back = screen.getByRole('link', { name: 'Schedule' })
  expect(back).toHaveAttribute('href', `#/engagements/${engagement.id}`)
  act(() => {
    window.location.hash = back.getAttribute('href') ?? ''
  })
  expect(await screen.findByRole('heading', { name: engagement.label })).toBeInTheDocument()
})

test('the schedule opens the evaluation of the same engagement, which leads back to it', async () => {
  // The evaluation fixtures and the schedule fixtures are of different engagements, so
  // each address is given the answers of its own engagement.
  window.location.hash = `#/engagements/${engagement.id}`
  mockApi({ 'GET /api/health': HEALTH, ...SCHEDULE, ...evaluationAnswers(clearNoRun) })
  render(<App />)
  const link = await screen.findByRole('link', { name: 'Evaluation' })
  expect(link).toHaveAttribute('href', `#/engagements/${engagement.id}/evaluation`)

  act(() => {
    window.location.hash = `#/engagements/${clearNoRun.engagement.id}/evaluation`
  })
  expect(
    await screen.findByRole('heading', { level: 1, name: clearNoRun.engagement.label }),
  ).toBeInTheDocument()
  expect(screen.getByText('Evaluation of uncorrected misstatements')).toBeInTheDocument()
  expect(screen.getByRole('region', { name: 'Gates and sign-off' })).toBeInTheDocument()
  expect(screen.queryByRole('table', { name: 'Schedule of misstatements' })).not.toBeInTheDocument()
  const nav = screen.getByRole('navigation', { name: 'Main' })
  expect(within(nav).getByRole('link', { name: 'Engagements' })).not.toHaveAttribute('aria-current')

  const back = screen.getByRole('link', { name: 'Back to the schedule' })
  expect(back).toHaveAttribute('href', `#/engagements/${clearNoRun.engagement.id}`)
  act(() => {
    window.location.hash = `#/engagements/${engagement.id}`
  })
  expect(
    await screen.findByRole('table', { name: 'Schedule of misstatements' }),
  ).toBeInTheDocument()
})

test('a move made on the detail page shows on the schedule when it is opened again', async () => {
  const id = workflowEngagement.id
  window.location.hash = `#/engagements/${id}`
  mockApi({
    'GET /api/health': HEALTH,
    ...scheduleAnswers(id, workflowScheduleRaised),
    [detailPath(raised)]: raised,
    [transitionPath(raised)]: answered(201, toCommunicated),
  })
  render(<App />)
  const schedule = () => screen.getByRole('table', { name: 'Schedule of misstatements' })
  const reference = await screen.findByRole('link', { name: 'M-1' })
  expect(within(schedule()).getByText('Raised')).toBeInTheDocument()

  act(() => {
    window.location.hash = reference.getAttribute('href') ?? ''
  })
  await screen.findByRole('heading', { level: 1, name: 'M-1' })
  fireEvent.click(screen.getByRole('button', { name: 'Mark as communicated' }))
  fireEvent.click(screen.getByRole('button', { name: 'Confirm: communicated' }))
  expect(await screen.findByText('Recorded: M-1 is now communicated.')).toBeInTheDocument()

  // From here on the backend answers with the schedule as it stands after the move.
  mockApi({ 'GET /api/health': HEALTH, ...scheduleAnswers(id, workflowScheduleCommunicated) })
  const back = screen.getByRole('link', { name: 'Back to the schedule' })
  expect(back).toHaveAttribute('href', `#/engagements/${id}`)
  act(() => {
    window.location.hash = back.getAttribute('href') ?? ''
  })
  expect(await screen.findByRole('heading', { name: workflowEngagement.label })).toBeInTheDocument()
  // The schedule was read again, not remembered: it shows the new state.
  expect(requested().sort()).toEqual(
    [
      `GET /api/engagements/${id}`,
      `GET /api/engagements/${id}/evaluation`,
      `GET /api/engagements/${id}/misstatements`,
    ].sort(),
  )
  expect(within(schedule()).getByText('Communicated')).toBeInTheDocument()
  expect(within(schedule()).queryByText('Raised')).not.toBeInTheDocument()
})

test('an address that is not a screen shows the engagement list', async () => {
  window.location.hash = '#/nowhere/at/all'
  mockApi({ 'GET /api/health': HEALTH, 'GET /api/engagements': engagements })
  render(<App />)
  expect(await screen.findByRole('heading', { name: 'Engagements' })).toBeInTheDocument()
})

test('the page still works when the backend health check fails but the list loads', async () => {
  mockApi({ 'GET /api/engagements': engagements })
  render(<App />)
  expect(await screen.findByRole('table')).toBeInTheDocument()
  expect(await screen.findByText('Backend unreachable: start it on port 8003.')).toBeInTheDocument()
})

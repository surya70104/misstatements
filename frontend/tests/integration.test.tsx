// The screens together (Stage 6 part 5): one path through every screen, every link checked,
// and every amount on every screen traced back to the API, digit for digit. The fixtures are
// the backend's real answers for one engagement (backend/tests/test_frontend_fixtures.py).
import { act, configure, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterAll, afterEach, beforeAll, expect, test, vi } from 'vitest'

import type { Engagement } from '../src/api'
import { App } from '../src/App'
import { EvaluationPage } from '../src/pages/EvaluationPage'
import { MisstatementPage } from '../src/pages/MisstatementPage'
import { SchedulePage } from '../src/pages/SchedulePage'
import { parseRoute } from '../src/router'
import {
  classificationDrift,
  communicatedJudgemental,
  corrected,
  detailPath,
  raised,
  workflowEngagement,
  workflowScheduleRaised,
} from './detailFixtures'
import {
  concluded,
  evaluationAnswers,
  hardGate,
  partnerAvailable,
  twoConclusions,
  twoRuns,
  type Snapshot,
} from './evaluationFixtures'
import {
  spineAnswers,
  thresholdsAnswers,
  workflowSpine,
  workflowThresholds,
} from './closureFixtures'
import listJson from './fixtures/workflow-engagements.json'
import screenJson from './fixtures/workflow-evaluation-screen.json'
import { mockApi, requested } from './mockApi'
import {
  SCHEDULE,
  engagement,
  misstatements,
  evaluation,
  scheduleAnswers,
} from './scheduleFixtures'

const listed = listJson as Engagement[]
const evaluationScreen = screenJson as unknown as Snapshot
const HEALTH = { status: 'ok', module: 'misstatements-rollup', version: '0.1.0' }

// Everything the backend answers for the one engagement, on every screen.
const EVERYTHING = {
  'GET /api/health': HEALTH,
  'GET /api/engagements': listed,
  ...scheduleAnswers(workflowEngagement.id, workflowScheduleRaised),
  ...evaluationAnswers(evaluationScreen),
  ...thresholdsAnswers(workflowThresholds),
  ...spineAnswers(workflowSpine),
  [detailPath(raised)]: raised,
}

// These tests load many screens one after another. On a busy machine one load can take
// longer than the one second a wait allows by default, so the waits here are given more.
const PATIENCE = 5000
const LONG_TEST = 30000

beforeAll(() => {
  configure({ asyncUtilTimeout: PATIENCE })
})

afterAll(() => {
  configure({ asyncUtilTimeout: 1000 })
})

afterEach(() => {
  vi.unstubAllGlobals()
  window.location.hash = ''
})

/** Go where a link points: jsdom does not follow an href by itself. */
function follow(link: HTMLElement) {
  const target = link.getAttribute('href')
  if (target === null) throw new Error('the link has no address')
  act(() => {
    window.location.hash = target
  })
}

async function heading(name: string) {
  return screen.findByRole('heading', { level: 1, name })
}

// ---- navigation ----

test('the fixtures of the path belong to one engagement', () => {
  const id = workflowEngagement.id
  expect(listed.map((entry) => entry.id)).toEqual([id])
  expect(evaluationScreen.engagement.id).toBe(id)
  expect(raised.engagement_id).toBe(id)
  expect(workflowScheduleRaised.misstatements.map((entry) => entry.id)).toEqual([raised.id])
})

test(
  'one path leads through every screen and back, by the links on the screens',
  async () => {
    const id = workflowEngagement.id
    const label = workflowEngagement.label
    mockApi(EVERYTHING)
    render(<App />)

    // Engagement list -> Schedule
    // The list shows its heading while it loads, so wait for the engagement itself.
    await heading('Engagements')
    follow(await screen.findByRole('link', { name: label }))
    await heading(label)
    expect(screen.getByRole('table', { name: 'Schedule of misstatements' })).toBeInTheDocument()
    expect(window.location.hash).toBe(`#/engagements/${id}`)

    // Schedule -> Misstatement detail
    follow(screen.getByRole('link', { name: 'M-1' }))
    await heading('M-1')
    expect(screen.getByRole('region', { name: 'State history' })).toBeInTheDocument()
    expect(window.location.hash).toBe(`#/misstatements/${raised.id}`)

    // Detail -> Schedule, by the button and, the second time, by the breadcrumb
    follow(screen.getByRole('link', { name: 'Back to the schedule' }))
    await heading(label)
    expect(window.location.hash).toBe(`#/engagements/${id}`)
    follow(screen.getByRole('link', { name: 'M-1' }))
    await heading('M-1')
    follow(screen.getByRole('link', { name: 'Schedule' }))
    await heading(label)
    expect(screen.getByRole('table', { name: 'Schedule of misstatements' })).toBeInTheDocument()

    // Schedule -> Evaluation
    follow(screen.getByRole('link', { name: 'Evaluation' }))
    await screen.findByRole('region', { name: 'Gates and sign-off' })
    expect(screen.getByRole('heading', { level: 1, name: label })).toBeInTheDocument()
    expect(window.location.hash).toBe(`#/engagements/${id}/evaluation`)

    // Evaluation -> Schedule, by the button and, the second time, by the breadcrumb
    follow(screen.getByRole('link', { name: 'Back to the schedule' }))
    await screen.findByRole('table', { name: 'Schedule of misstatements' })
    follow(screen.getByRole('link', { name: 'Evaluation' }))
    await screen.findByRole('region', { name: 'Gates and sign-off' })
    follow(screen.getByRole('link', { name: label }))
    await screen.findByRole('table', { name: 'Schedule of misstatements' })

    // And home: the title and the navigation both lead to the engagement list.
    follow(within(screen.getByRole('navigation', { name: 'Main' })).getByRole('link'))
    await heading('Engagements')
    expect(await screen.findByRole('link', { name: label })).toBeInTheDocument()

    // The whole path was read, and nothing was written.
    expect(requested().filter((request) => !request.startsWith('GET'))).toEqual([])
  },
  LONG_TEST,
)

test(
  'every link on every screen leads to a screen that loads',
  async () => {
    mockApi(EVERYTHING)
    render(<App />)
    await heading('Engagements')

    const seen = new Set<string>()
    const queue = ['#/']
    while (queue.length > 0) {
      const address = queue.shift()
      if (address === undefined || seen.has(address)) continue
      seen.add(address)
      act(() => {
        window.location.hash = address
      })
      // The address is one the router knows: an unknown one would fall back to the list.
      if (address !== '#/') expect(parseRoute(address).name).not.toBe('engagements')
      await screen.findByRole('heading', { level: 1 })
      // It loaded: no failure, and nothing still loading inside the page.
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
      // The engagement list shows its heading while it loads, so wait for the load itself.
      await waitFor(() => {
        expect(within(screen.getByRole('main')).queryByText(/^Loading/)).not.toBeInTheDocument()
      })
      for (const link of screen.getAllByRole('link')) {
        const target = link.getAttribute('href')
        expect(target, `"${link.textContent}" has no address`).toMatch(/^#\//)
        if (target !== null) queue.push(target)
      }
    }

    const id = workflowEngagement.id
    expect([...seen].sort()).toEqual(
      [
        '#/',
        '#/engagements/new',
        `#/engagements/${id}`,
        `#/engagements/${id}/evaluation`,
        `#/engagements/${id}/thresholds`,
        `#/engagements/${id}/spine`,
        `#/engagements/${id}/events`,
        `#/engagements/${id}/misstatements/new`,
        `#/misstatements/${raised.id}`,
      ].sort(),
    )
    expect(requested().filter((request) => !request.startsWith('GET'))).toEqual([])
  },
  LONG_TEST,
)

test('no link leaves the application or opens another window', async () => {
  mockApi(EVERYTHING)
  window.location.hash = `#/engagements/${workflowEngagement.id}/evaluation`
  render(<App />)
  await screen.findByRole('region', { name: 'Gates and sign-off' })
  for (const link of screen.getAllByRole('link')) {
    expect(link).not.toHaveAttribute('target')
    expect(link.getAttribute('href')).not.toMatch(/^https?:|^\/\//)
  }
})

// ---- exact decimal precision ----

/** Every exact decimal amount anywhere in the backend's answers. */
function amountsIn(...answers: unknown[]): Set<string> {
  const found = new Set<string>()
  const walk = (value: unknown) => {
    if (typeof value === 'string') {
      if (/^-?\d+\.\d{2}$/.test(value)) found.add(value)
    } else if (Array.isArray(value)) {
      value.forEach(walk)
    } else if (typeof value === 'object' && value !== null) {
      Object.values(value).forEach(walk)
    }
  }
  answers.forEach(walk)
  return found
}

/** Every rupee amount on the screen, with its formatting taken off again. */
function amountsShown(): string[] {
  // Read piece of text by piece of text: neighbouring cells have no space between them, and
  // an amount must not be run together with the figure in the next cell.
  const shown: string[] = []
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
  while (walker.nextNode()) {
    const text = walker.currentNode.textContent ?? ''
    for (const match of text.matchAll(/(-?)₹([\d,]+(?:\.\d+)?)/g)) {
      shown.push(`${match[1] ?? ''}${(match[2] ?? '').replaceAll(',', '')}`)
    }
  }
  return shown
}

function expectEveryAmountIsTheBackends(shown: string[], sent: Set<string>) {
  expect(shown.length).toBeGreaterThan(0)
  for (const amount of shown) {
    // Exactly two decimals, never rounded, never a figure the backend did not send.
    expect(amount).toMatch(/^-?\d+\.\d{2}$/)
    expect(sent, `${amount} is shown but was not sent by the backend`).toContain(amount)
  }
}

test('every amount on the schedule is one the backend sent, digit for digit', async () => {
  mockApi(SCHEDULE)
  render(<SchedulePage id={engagement.id} />)
  await screen.findByRole('table', { name: 'Schedule of misstatements' })
  const shown = amountsShown()
  expectEveryAmountIsTheBackends(shown, amountsIn(misstatements, evaluation))
  // Seven misstatements with two lines and two effects each, and the totals above them.
  expect(shown.length).toBeGreaterThanOrEqual(7 * 4 + 4)
  expect(shown).toContain('-195000.00')
})

test(
  'every amount on the misstatement detail is one the backend sent, digit for digit',
  async () => {
    for (const misstatement of [raised, corrected, communicatedJudgemental, classificationDrift]) {
      mockApi({ [detailPath(misstatement)]: misstatement })
      const view = render(<MisstatementPage id={misstatement.id} />)
      await screen.findByRole('region', { name: 'Financial effects' })
      expectEveryAmountIsTheBackends(amountsShown(), amountsIn(misstatement))
      view.unmount()
    }
  },
  LONG_TEST,
)

test(
  'every amount on the evaluation is one the backend sent, digit for digit',
  async () => {
    for (const snapshot of [hardGate, twoRuns, twoConclusions, partnerAvailable, concluded]) {
      mockApi(evaluationAnswers(snapshot))
      const view = render(<EvaluationPage id={snapshot.engagement.id} />)
      await screen.findByRole('region', { name: 'Gates and sign-off' })
      // Open every run, so what a run recorded is checked too.
      for (const run of snapshot.runs) {
        fireEvent.click(screen.getByRole('button', { name: `Inspect run ${String(run.run_no)}` }))
        expectEveryAmountIsTheBackends(amountsShown(), amountsIn(snapshot))
      }
      expectEveryAmountIsTheBackends(amountsShown(), amountsIn(snapshot))
      view.unmount()
    }
  },
  LONG_TEST,
)

test('the only numbers the screens compute are percentages, and those are exact', async () => {
  mockApi(evaluationAnswers(hardGate))
  render(<EvaluationPage id={hardGate.engagement.id} />)
  const table = await screen.findByRole('table', {
    name: /^Aggregate uncorrected misstatements, with/,
  })
  const row = within(table).getByRole('row', { name: /^Profit before tax gross/ })
  // 4,00,000 against 12,500, 2,50,000 and 4,00,000: exactly 3,200%, 160% and 100%.
  expect(row).toHaveTextContent('3,200.0%')
  expect(row).toHaveTextContent('160.0%')
  expect(row).toHaveTextContent('100.0%')
})

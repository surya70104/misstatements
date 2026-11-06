// Accessibility of the application as a whole (register S12): every screen says what it is
// in the page title, keyboard focus follows the screen, the content can be reached without
// tabbing through the header, the tabs say which screen is in view, and every control has a
// name. Contrast and layout are checked in a browser, which a test here cannot do.
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import html from '../index.html?raw'
import icon from '../public/favicon.svg?raw'
import type { Engagement } from '../src/api'
import { App } from '../src/App'
import { RunningTotals } from '../src/components/RunningTotals'
import {
  spineAnswers,
  thresholdsAnswers,
  workflowSpine,
  workflowThresholds,
} from './closureFixtures'
import { detailPath, raised, workflowEngagement, workflowScheduleRaised } from './detailFixtures'
import { evaluationAnswers, type Snapshot } from './evaluationFixtures'
import listJson from './fixtures/workflow-engagements.json'
import screenJson from './fixtures/workflow-evaluation-screen.json'
import { mockApi } from './mockApi'
import { evaluation, scheduleAnswers } from './scheduleFixtures'

const listed = listJson as Engagement[]
const evaluationScreen = screenJson as unknown as Snapshot
const id = workflowEngagement.id
const label = workflowEngagement.label

const EVERYTHING = {
  'GET /api/health': { status: 'ok', module: 'misstatements-rollup', version: '0.1.0' },
  'GET /api/engagements': listed,
  ...scheduleAnswers(id, workflowScheduleRaised),
  ...evaluationAnswers(evaluationScreen),
  ...thresholdsAnswers(workflowThresholds),
  ...spineAnswers(workflowSpine),
  [detailPath(raised)]: raised,
}

afterEach(() => {
  vi.unstubAllGlobals()
  window.location.hash = ''
  document.title = ''
})

function go(address: string) {
  act(() => {
    window.location.hash = address
  })
}

async function loaded() {
  await screen.findByRole('heading', { level: 1 })
  await waitFor(() => {
    expect(within(screen.getByRole('main')).queryByText(/^Loading/)).not.toBeInTheDocument()
  })
}

// ---- page titles ----

test('every screen names itself in the page title', async () => {
  mockApi(EVERYTHING)
  render(<App />)
  const titles: [string, string][] = [
    ['#/', 'Engagements · Misstatements Rollup'],
    ['#/engagements/new', 'New engagement · Misstatements Rollup'],
    [`#/engagements/${id}`, `Schedule · ${label} · Misstatements Rollup`],
    [`#/engagements/${id}/evaluation`, `Evaluation · ${label} · Misstatements Rollup`],
    [`#/engagements/${id}/thresholds`, `Thresholds · ${label} · Misstatements Rollup`],
    [`#/engagements/${id}/spine`, `Financial Spine · ${label} · Misstatements Rollup`],
    [`#/engagements/${id}/events`, `Events · ${label} · Misstatements Rollup`],
    [
      `#/engagements/${id}/misstatements/new`,
      `Record a misstatement · ${label} · Misstatements Rollup`,
    ],
    [`#/misstatements/${raised.id}`, 'Misstatement M-1 · Misstatements Rollup'],
  ]
  for (const [address, title] of titles) {
    go(address)
    await loaded()
    await waitFor(() => {
      expect(document.title).toBe(title)
    })
  }
  // No two screens share a title.
  expect(new Set(titles.map(([, title]) => title)).size).toBe(titles.length)
})

test('a screen that is still loading or failed still has a title of its own', async () => {
  mockApi({})
  window.location.hash = `#/engagements/${id}/thresholds`
  render(<App />)
  await screen.findByRole('alert')
  expect(document.title).toBe('Thresholds · Misstatements Rollup')
})

// ---- keyboard focus ----

test('when the screen changes, focus moves to its content; not on the first load', async () => {
  mockApi(EVERYTHING)
  render(<App />)
  await loaded()
  const main = screen.getByRole('main')
  // On the first load focus is left where the browser put it.
  expect(document.activeElement).not.toBe(main)

  go(`#/engagements/${id}`)
  await loaded()
  expect(document.activeElement).toBe(main)

  // Focus moved by a person stays moved until the screen changes again.
  const reference = screen.getByRole('link', { name: 'M-1' })
  reference.focus()
  expect(document.activeElement).toBe(reference)
  go(`#/misstatements/${raised.id}`)
  await loaded()
  expect(document.activeElement).toBe(screen.getByRole('main'))
})

test('the content can be reached in one step, without tabbing through the header', async () => {
  mockApi(EVERYTHING)
  render(<App />)
  await loaded()
  const skip = screen.getByRole('button', { name: 'Skip to the content' })
  // It is the first thing a keyboard reaches.
  const focusable = [...document.querySelectorAll<HTMLElement>('a[href], button, [tabindex]')]
  expect(focusable[0]).toBe(skip)
  fireEvent.click(skip)
  expect(document.activeElement).toBe(screen.getByRole('main'))
  // The main region takes focus from a script but is not a tab stop of its own.
  expect(screen.getByRole('main')).toHaveAttribute('tabindex', '-1')
})

// ---- navigation within an engagement ----

test('every screen of an engagement leads to every other, and says which one is in view', async () => {
  mockApi(EVERYTHING)
  render(<App />)
  const tabs: [string, string][] = [
    ['Schedule', `#/engagements/${id}`],
    ['Evaluation', `#/engagements/${id}/evaluation`],
    ['Thresholds', `#/engagements/${id}/thresholds`],
    ['Financial Spine', `#/engagements/${id}/spine`],
    ['Events', `#/engagements/${id}/events`],
  ]
  for (const [current, address] of tabs) {
    go(address)
    await loaded()
    const nav = screen.getByRole('navigation', { name: 'Engagement' })
    const links = within(nav).getAllByRole('link')
    expect(links.map((link) => [link.textContent, link.getAttribute('href')])).toEqual(tabs)
    expect(
      links
        .filter((link) => link.getAttribute('aria-current') === 'page')
        .map((l) => l.textContent),
    ).toEqual([current])
  }
})

test('the schedule leads to recording a misstatement, and the list to a new engagement', async () => {
  mockApi(EVERYTHING)
  render(<App />)
  await loaded()
  expect(await screen.findByRole('link', { name: 'New engagement' })).toHaveAttribute(
    'href',
    '#/engagements/new',
  )
  go(`#/engagements/${id}`)
  await loaded()
  expect(screen.getByRole('link', { name: 'Record a misstatement' })).toHaveAttribute(
    'href',
    `#/engagements/${id}/misstatements/new`,
  )
})

// ---- names and labels ----

test('every control on every screen has a name, and every field a label', async () => {
  mockApi(EVERYTHING)
  render(<App />)
  for (const address of [
    '#/',
    '#/engagements/new',
    `#/engagements/${id}`,
    `#/engagements/${id}/evaluation`,
    `#/engagements/${id}/thresholds`,
    `#/engagements/${id}/spine`,
    `#/engagements/${id}/events`,
    `#/engagements/${id}/misstatements/new`,
    `#/misstatements/${raised.id}`,
  ]) {
    go(address)
    await loaded()
    for (const control of document.querySelectorAll<HTMLElement>('a, button')) {
      const name = control.getAttribute('aria-label') ?? control.textContent
      expect(name.trim(), `${address}: ${control.outerHTML.slice(0, 80)}`).not.toBe('')
    }
    for (const field of document.querySelectorAll<HTMLInputElement>('input, select, textarea')) {
      const labelled =
        field.labels !== null && field.labels.length > 0 ? true : field.hasAttribute('aria-label')
      expect(labelled, `${address}: ${field.outerHTML.slice(0, 80)}`).toBe(true)
    }
    // Every table says what it is, and no id is used twice.
    for (const table of document.querySelectorAll('table')) {
      expect(table.querySelector('caption'), `${address}: a table has no caption`).not.toBeNull()
    }
    const ids = [...document.querySelectorAll('[id]')].map((element) => element.id)
    expect(
      ids.filter((value, index) => ids.indexOf(value) !== index),
      address,
    ).toEqual([])
    // One main heading, and no level skipped below it.
    const levels = [...document.querySelectorAll('h1, h2, h3, h4')].map((heading) =>
      Number(heading.tagName.slice(1)),
    )
    expect(
      levels.filter((level) => level === 1),
      address,
    ).toHaveLength(1)
    levels.forEach((level, index) => {
      if (index > 0) expect(level - (levels[index - 1] ?? level), address).toBeLessThanOrEqual(1)
    })
  }
})

// ---- the favicon and the totals ----

test('the page declares a favicon, and the file it names exists', () => {
  expect(html).toContain('<link rel="icon" type="image/svg+xml" href="/favicon.svg" />')
  expect(icon).toContain('<svg')
  expect(html).toContain('<html lang="en">')
})

test('the running totals stay in view at every width, a phone included', () => {
  render(<RunningTotals evaluation={evaluation} />)
  const totals = screen.getByRole('region', { name: 'Running totals: uncorrected misstatements' })
  // Pinned without a width condition: "always visible" (spec section 10.1).
  expect(totals.className.split(/\s+/)).toContain('sticky')
  expect(totals.className).not.toMatch(/\b(sm|md|lg|xl):sticky\b/)
  // A phone shows a short name; a screen reader is given the full one in its place.
  const row = within(totals).getByRole('row', { name: /^Profit before tax gross/ })
  expect(within(row).getByText('PBT')).toHaveAttribute('aria-hidden', 'true')
})

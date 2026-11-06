// The engagement list against the backend's real answers: the fixtures in tests/fixtures
// are written by backend/tests/test_frontend_fixtures.py and checked there against the API.
import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import type { Engagement } from '../src/api'
import { dateTime } from '../src/format'
import { EngagementsPage } from '../src/pages/EngagementsPage'
import fixture from './fixtures/engagements.json'
import { failApi, mockApi, refusal, requested } from './mockApi'

const engagements = fixture as Engagement[]

afterEach(() => {
  vi.unstubAllGlobals()
})

function rowOf(label: string): HTMLElement {
  const row = screen.getByRole('link', { name: label }).closest('tr')
  if (row === null) throw new Error(`no row for ${label}`)
  return row
}

test('it says it is loading, then lists every engagement the backend sent', async () => {
  mockApi({ 'GET /api/engagements': engagements })
  render(<EngagementsPage />)
  expect(screen.getByRole('status')).toHaveTextContent('Loading the engagements…')
  expect(await screen.findByRole('table')).toBeInTheDocument()
  expect(screen.queryByRole('status')).not.toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Engagements' })).toBeInTheDocument()
  expect(screen.getByText('3 engagements')).toBeInTheDocument()
  for (const engagement of engagements) {
    expect(screen.getByRole('link', { name: engagement.label })).toBeInTheDocument()
  }
  expect(screen.getAllByRole('row')).toHaveLength(engagements.length + 1) // and the header
  expect(requested()).toEqual(['GET /api/engagements'])
})

test('each row shows the backend’s values and nothing computed here', async () => {
  mockApi({ 'GET /api/engagements': engagements })
  render(<EngagementsPage />)
  await screen.findByRole('table')
  const [pinned, linked, unlinked] = engagements
  if (!pinned || !linked || !unlinked) throw new Error('the fixture holds three engagements')

  const first = within(rowOf(pinned.label))
  expect(first.getByText('Linked, version pinned')).toBeInTheDocument()
  expect(first.getByText(String(pinned.misstatements))).toBeInTheDocument()
  expect(first.getByText('Set')).toBeInTheDocument()
  expect(first.getByText(pinned.created_by)).toBeInTheDocument()
  expect(first.getByText(dateTime(pinned.created_at))).toBeInTheDocument()

  const second = within(rowOf(linked.label))
  expect(second.getByText('Linked, no version pinned')).toBeInTheDocument()
  expect(second.getByText('0')).toBeInTheDocument()
  expect(second.getByText('Not set')).toBeInTheDocument()

  expect(within(rowOf(unlinked.label)).getByText('Not linked')).toBeInTheDocument()
})

test('each engagement links to its schedule', async () => {
  mockApi({ 'GET /api/engagements': engagements })
  render(<EngagementsPage />)
  await screen.findByRole('table')
  for (const engagement of engagements) {
    expect(screen.getByRole('link', { name: engagement.label })).toHaveAttribute(
      'href',
      `#/engagements/${engagement.id}`,
    )
  }
})

test('the table is labelled for a screen reader', async () => {
  mockApi({ 'GET /api/engagements': engagements })
  render(<EngagementsPage />)
  const table = await screen.findByRole('table')
  expect(table).toHaveAccessibleName(/Engagements, each with its Financial Spine link/)
  expect(
    within(table)
      .getAllByRole('columnheader')
      .map((cell) => cell.textContent),
  ).toEqual([
    'Engagement',
    'Financial Spine',
    'Misstatements',
    'Thresholds',
    'Created by',
    'Created',
  ])
  expect(within(table).getAllByRole('rowheader')).toHaveLength(engagements.length)
})

test('an empty list says so and shows no table', async () => {
  mockApi({ 'GET /api/engagements': [] })
  render(<EngagementsPage />)
  expect(await screen.findByText('No engagements yet')).toBeInTheDocument()
  expect(screen.getByText('0 engagements')).toBeInTheDocument()
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})

test('one engagement is counted in the singular', async () => {
  mockApi({ 'GET /api/engagements': engagements.slice(0, 1) })
  render(<EngagementsPage />)
  expect(await screen.findByText('1 engagement')).toBeInTheDocument()
})

test('a refusal is shown in the backend’s words with the request it came from', async () => {
  mockApi({
    'GET /api/engagements': refusal(503, { detail: 'the database is not available' }),
  })
  render(<EngagementsPage />)
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent('The engagements could not be loaded')
  expect(alert).toHaveTextContent('the database is not available')
  expect(alert).toHaveTextContent('/api/engagements answered 503')
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
  expect(screen.queryByText('No engagements yet')).not.toBeInTheDocument() // an error is not "none"
})

test('an unreachable backend is explained, and trying again loads the list', async () => {
  failApi()
  render(<EngagementsPage />)
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent('The backend could not be reached.')
  expect(alert).not.toHaveTextContent('answered')

  mockApi({ 'GET /api/engagements': engagements })
  fireEvent.click(within(alert).getByRole('button', { name: 'Try again' }))
  expect(await screen.findByRole('table')).toBeInTheDocument()
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  expect(requested()).toEqual(['GET /api/engagements'])
})

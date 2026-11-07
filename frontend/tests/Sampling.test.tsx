// Projected misstatements from Sampling on the screens (SA 530; spec section 3.2; backend
// D65): the record form asks how a projected item was projected, the detail shows it, and
// the schedule says which items are projected. The fixtures are the backend's real answers
// (backend/tests/test_frontend_fixtures.py).
import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { MisstatementPage } from '../src/pages/MisstatementPage'
import { RaiseMisstatementPage } from '../src/pages/RaiseMisstatementPage'
import { SchedulePage } from '../src/pages/SchedulePage'
import { createdPinned, misstatementRaised } from './closureFixtures'
import { communicatedProjected, detailPath, raised } from './detailFixtures'
import { answered, mockApi, requested, sent } from './mockApi'
import { misstatements, SCHEDULE, engagement as scheduleEngagement } from './scheduleFixtures'

afterEach(() => {
  vi.unstubAllGlobals()
  window.location.hash = ''
})

const pinned = createdPinned
const raisePath = `POST /api/engagements/${pinned.id}/misstatements`

async function openRaise(answers: Record<string, unknown> = {}) {
  mockApi({ [`GET /api/engagements/${pinned.id}`]: pinned, ...answers })
  render(<RaiseMisstatementPage id={pinned.id} />)
  await screen.findByRole('heading', { level: 1, name: 'Record a misstatement' })
}

function type(label: string | RegExp, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } })
}

const record = () => screen.getByRole('button', { name: 'Record misstatement' })

function fillProjected() {
  fireEvent.change(screen.getByLabelText(/^Type/), { target: { value: 'projected' } })
  type(/^Description/, 'Sales cut-off errors projected over the March population')
  type(/^Working paper reference/, 'R-5.3')
  type('Line 1 import line number', '4')
  type('Line 1 amount', '40000.00')
  type('Line 2 import line number', '1')
  type('Line 2 amount', '40000.00')
  type(/^Sample \(/, 'S-12')
  type(/^Projection basis/, 'Ratio of error to sample value, applied to the population')
}

function fillSampling() {
  type(/^Population value/, '4000000.00')
  type(/^Items in the population/, '1200')
  type(/^Sample value/, '400000.00')
  type(/^Items in the sample/, '120')
  type(/^Misstatement found in the sample/, '4000.00')
  type(/^Projected amount/, '40000.00')
}

// ---- the record form ----

test('choosing the projected type asks how it was projected, and nothing else does', async () => {
  await openRaise()
  expect(screen.queryByRole('group', { name: /^How it was projected/ })).not.toBeInTheDocument()
  fireEvent.change(screen.getByLabelText(/^Type/), { target: { value: 'projected' } })
  const sampling = screen.getByRole('group', { name: /^How it was projected \(SA 530\)/ })
  expect(sampling).toHaveTextContent('The Dr/Cr lines below carry the projected amount')
  const method = screen.getByLabelText(/^Sampling method/)
  expect(
    within(method)
      .getAllByRole('option')
      .map((option) => option.textContent),
  ).toEqual([
    'Ratio estimation',
    'Difference estimation',
    'Mean-per-unit estimation',
    'Monetary-unit sampling',
    'Other, described in the projection basis',
  ])
  for (const label of [
    /^Population value/,
    /^Items in the population/,
    /^Sample value/,
    /^Items in the sample/,
    /^Misstatement found in the sample/,
    /^Projected amount/,
  ]) {
    // Each is asked for; the record button stays disabled until every one is given.
    expect(screen.getByLabelText(label)).toBeInTheDocument()
  }
  fireEvent.change(screen.getByLabelText(/^Type/), { target: { value: 'judgemental' } })
  expect(screen.queryByRole('group', { name: /^How it was projected/ })).not.toBeInTheDocument()
})

test('a projected misstatement cannot be sent until every sampling figure is given and well formed', async () => {
  await openRaise()
  fillProjected()
  expect(record()).toBeDisabled()
  fillSampling()
  expect(record()).toBeEnabled()
  for (const [label, wrong] of [
    [/^Items in the population/, '0'],
    [/^Items in the population/, '12.5'],
    [/^Items in the sample/, 'twelve'],
    [/^Population value/, '4,000,000'],
    [/^Projected amount/, '40000.005'],
    [/^Misstatement found in the sample/, ''],
  ] as const) {
    fireEvent.change(screen.getByLabelText(label), { target: { value: wrong } })
    expect(record(), `${String(label)} = ${wrong}`).toBeDisabled()
    fillSampling()
    expect(record()).toBeEnabled()
  }
  fireEvent.change(screen.getByLabelText(/^Items in the population/), { target: { value: '' } })
  fireEvent.submit(screen.getByRole('form', { name: 'Record a misstatement' }))
  expect(requested().filter((request) => request.startsWith('POST'))).toEqual([])
})

test('the sampling figures are sent as typed, with the method and the projected amount', async () => {
  await openRaise({ [raisePath]: answered(201, misstatementRaised) })
  fillProjected()
  fillSampling()
  // A negative misstatement in the sample is a figure too.
  type(/^Misstatement found in the sample/, '-4000.00')
  fireEvent.change(screen.getByLabelText(/^Sampling method/), {
    target: { value: 'monetary_unit' },
  })
  fireEvent.click(record())
  await vi.waitFor(() => {
    expect(window.location.hash).toBe(`#/misstatements/${misstatementRaised.id}`)
  })
  expect(sent()[0]?.body).toMatchObject({
    type: 'projected',
    sample_ref: 'S-12',
    projection_basis: 'Ratio of error to sample value, applied to the population',
    sampling_method: 'monetary_unit',
    population_value: '4000000.00',
    population_size: 1200,
    sample_value: '400000.00',
    sample_size: 120,
    known_error_in_sample: '-4000.00',
    projected_amount: '40000.00',
    lines: [
      { line_no: 4, dr: '40000.00' },
      { line_no: 1, cr: '40000.00' },
    ],
  })
  // Amounts are strings, counts are whole numbers; nothing passes through floating point.
  const body = sent()[0]?.body as Record<string, unknown>
  expect(typeof body.population_value).toBe('string')
  expect(Number.isInteger(body.population_size)).toBe(true)
})

test('a factual misstatement sends no sampling figure, even after the type is changed back', async () => {
  await openRaise({ [raisePath]: answered(201, misstatementRaised) })
  fillProjected()
  fillSampling()
  fireEvent.change(screen.getByLabelText(/^Type/), { target: { value: 'factual' } })
  fireEvent.click(record())
  await vi.waitFor(() => {
    expect(requested().filter((request) => request.startsWith('POST'))).toHaveLength(1)
  })
  const body = sent()[0]?.body as Record<string, unknown>
  for (const key of [
    'sample_ref',
    'projection_basis',
    'sampling_method',
    'population_value',
    'population_size',
    'sample_value',
    'sample_size',
    'known_error_in_sample',
    'projected_amount',
  ]) {
    expect(body).not.toHaveProperty(key)
  }
})

// ---- the detail ----

function fact(label: string): HTMLElement {
  const term = within(screen.getByRole('region', { name: 'Identification' })).getByText(label, {
    selector: 'dt',
  })
  return term.nextElementSibling as HTMLElement
}

test('a projected misstatement shows how it was projected from its sample', async () => {
  mockApi({ [detailPath(communicatedProjected)]: communicatedProjected })
  render(<MisstatementPage id={communicatedProjected.id} />)
  await screen.findByRole('heading', { level: 1, name: 'M-3' })
  expect(communicatedProjected.current.sampling).toEqual({
    method: 'ratio',
    population_value: '4000000.00',
    population_size: 1200,
    sample_value: '400000.00',
    sample_size: 120,
    known_error_in_sample: '4000.00',
  })
  expect(fact('Sample')).toHaveTextContent(/^S-12$/)
  expect(fact('Sampling method')).toHaveTextContent(/^Ratio estimation$/)
  expect(fact('Population value')).toHaveTextContent('₹40,00,000.00')
  expect(fact('Population value')).toHaveTextContent('1200 items')
  expect(fact('Sample value')).toHaveTextContent('₹4,00,000.00')
  expect(fact('Sample value')).toHaveTextContent('120 items')
  expect(fact('Misstatement found in the sample')).toHaveTextContent('₹4,000.00')
  expect(fact('Misstatement found in the sample')).toHaveTextContent(
    'The Dr/Cr lines carry the projected amount',
  )
  // No projected amount of its own is shown: the lines and the effects are the amount.
  expect(screen.queryByText('Projected amount')).not.toBeInTheDocument()
})

test('a factual misstatement shows no sampling detail', async () => {
  mockApi({ [detailPath(raised)]: raised })
  render(<MisstatementPage id={raised.id} />)
  await screen.findByRole('heading', { level: 1, name: 'M-1' })
  expect(raised.current.sampling).toBeNull()
  expect(screen.queryByText('Sampling method')).not.toBeInTheDocument()
})

// ---- the schedule ----

test('the schedule says which misstatements are projected, and from which sample', async () => {
  mockApi(SCHEDULE)
  render(<SchedulePage id={scheduleEngagement.id} />)
  await screen.findByRole('heading', { level: 1 })
  const table = screen.getByRole('table', { name: 'Schedule of misstatements' })
  const projected = misstatements.filter((item) => item.current.type === 'projected')
  expect(projected.length).toBeGreaterThan(0)
  for (const item of projected) {
    const row = within(table).getByRole('row', { name: new RegExp(`^${item.ref} `) })
    const cell = within(row)
      .getAllByRole('cell')
      .find((entry) => entry.getAttribute('data-label') === 'Type')
    expect(cell).toHaveTextContent(`ProjectedFrom sample ${item.current.sample_ref ?? ''}`)
  }
  for (const item of misstatements.filter((entry) => entry.current.type !== 'projected')) {
    const row = within(table).getByRole('row', { name: new RegExp(`^${item.ref} `) })
    expect(row).not.toHaveTextContent('From sample')
  }
})

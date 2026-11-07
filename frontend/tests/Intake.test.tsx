// Where a misstatement comes from, on the screens (spec section 8; backend D64): the record
// form takes each source with what it attaches, and the schedule and the detail show it.
// Every fixture is the backend's real answer (backend/tests/test_frontend_fixtures.py).
import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { MisstatementPage } from '../src/pages/MisstatementPage'
import { RaiseMisstatementPage } from '../src/pages/RaiseMisstatementPage'
import { SchedulePage } from '../src/pages/SchedulePage'
import {
  detailRun,
  engagement,
  evaluation,
  fromManual,
  fromNote,
  fromNoteGeneral,
  fromRun,
  misstatements,
  refusals,
} from './intakeFixtures'
import { answered, mockApi, refusal, requested, sent } from './mockApi'
import { scheduleAnswers } from './scheduleFixtures'

afterEach(() => {
  vi.unstubAllGlobals()
  window.location.hash = ''
})

const raisePath = `POST /api/engagements/${engagement.id}/misstatements`

async function openRaise(answers: Record<string, unknown> = {}) {
  mockApi({ [`GET /api/engagements/${engagement.id}`]: engagement, ...answers })
  render(<RaiseMisstatementPage id={engagement.id} />)
  await screen.findByRole('heading', { level: 1, name: 'Record a misstatement' })
}

function type(label: string | RegExp, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } })
}

function chooseSource(value: string) {
  fireEvent.change(screen.getByLabelText(/^Raised from/), { target: { value } })
}

function fillLines() {
  type(/^Description/, 'Sales of April booked in March')
  type('Line 1 import line number', '4')
  type('Line 1 amount', '40000.00')
  type('Line 2 import line number', '1')
  type('Line 2 amount', '40000.00')
}

const record = () => screen.getByRole('button', { name: 'Record misstatement' })

function posts(): string[] {
  return requested().filter((request) => request.startsWith('POST'))
}

// ---- the record form ----

test('every source of spec section 8 can be chosen, and each asks for what it attaches', async () => {
  await openRaise()
  const source = screen.getByLabelText(/^Raised from/)
  expect(
    within(source)
      .getAllByRole('option')
      .map((option) => option.textContent),
  ).toEqual(['A working paper', 'A WorkMind agent run', 'A review note', 'Manual entry'])
  // A working paper: its reference.
  expect(screen.getByLabelText(/^Working paper reference/)).toBeInTheDocument()
  expect(screen.queryByLabelText(/^Run id/)).not.toBeInTheDocument()
  // A run: its id and at least one citation; no working paper.
  chooseSource('run')
  expect(screen.queryByLabelText(/^Working paper reference/)).not.toBeInTheDocument()
  expect(screen.getByLabelText(/^Run id/)).toBeInTheDocument()
  expect(screen.getByRole('group', { name: /^Source-row citations/ })).toBeInTheDocument()
  expect(screen.getByLabelText('Citation 1 source')).toBeInTheDocument()
  expect(screen.getByLabelText('Citation 1 row')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /^Remove citation/ })).not.toBeInTheDocument()
  // A note: its reference and, optionally, a link.
  chooseSource('note')
  expect(screen.queryByLabelText(/^Run id/)).not.toBeInTheDocument()
  expect(screen.getByLabelText(/^Review note reference/)).toBeInTheDocument()
  expect(screen.getByLabelText(/^Link to the note/)).toBeInTheDocument()
  // A manual entry: a working paper reference, as the specification requires.
  chooseSource('manual')
  expect(screen.getByLabelText(/^Working paper reference/)).toBeInTheDocument()
  expect(screen.getByText('Required for a manual entry too.')).toBeInTheDocument()
})

test('a run cannot be sent without its id and a complete citation', async () => {
  await openRaise()
  chooseSource('run')
  fillLines()
  expect(record()).toBeDisabled()
  type(/^Run id/, 'run-2026-11-07-0042')
  expect(record()).toBeDisabled() // the citation is empty
  type('Citation 1 source', 'sales_register.csv')
  expect(record()).toBeDisabled() // and has no row yet
  type('Citation 1 row', '1042')
  expect(record()).toBeEnabled()
  // A second citation that is started must be completed too.
  fireEvent.click(screen.getByRole('button', { name: 'Add a citation' }))
  expect(record()).toBeDisabled()
  type('Citation 2 source', 'sales_register.csv')
  type('Citation 2 row', '1057')
  expect(record()).toBeEnabled()
  fireEvent.click(screen.getByRole('button', { name: 'Remove citation 2' }))
  expect(screen.queryByLabelText('Citation 2 source')).not.toBeInTheDocument()
  expect(record()).toBeEnabled()
  // Spaces are not a run id.
  type(/^Run id/, '   ')
  expect(record()).toBeDisabled()
  fireEvent.submit(screen.getByRole('form', { name: 'Record a misstatement' }))
  expect(posts()).toEqual([])
})

test('a run is sent with its id and citations, and no working paper reference', async () => {
  await openRaise({ [raisePath]: answered(201, fromRun) })
  chooseSource('run')
  fillLines()
  type(/^Run id/, ' run-2026-11-07-0042 ')
  type('Citation 1 source', 'sales_register.csv')
  type('Citation 1 row', '1042')
  type('Citation 1 detail', 'Invoice dated 2 April booked in March')
  fireEvent.click(screen.getByRole('button', { name: 'Add a citation' }))
  type('Citation 2 source', 'sales_register.csv')
  type('Citation 2 row', '1057')
  fireEvent.click(record())
  await vi.waitFor(() => {
    expect(window.location.hash).toBe(`#/misstatements/${fromRun.id}`)
  })
  expect(sent().map((entry) => entry.body)).toEqual([
    {
      type: 'factual',
      description: 'Sales of April booked in March',
      raised_from: 'run',
      run: {
        run_id: 'run-2026-11-07-0042',
        citations: [
          {
            source: 'sales_register.csv',
            row: '1042',
            detail: 'Invoice dated 2 April booked in March',
          },
          { source: 'sales_register.csv', row: '1057' },
        ],
      },
      lines: [
        { line_no: 4, dr: '40000.00' },
        { line_no: 1, cr: '40000.00' },
      ],
    },
  ])
  // What came back is what the backend recorded: the run and its citations, as sent.
  expect(fromRun.current.origin).toEqual({
    run_id: 'run-2026-11-07-0042',
    citations: [
      {
        source: 'sales_register.csv',
        row: '1042',
        detail: 'Invoice dated 2 April booked in March',
      },
      { source: 'sales_register.csv', row: '1057' },
    ],
  })
  expect(fromRun.current.state).toBe('raised')
})

test('a note is sent with its reference, and its link only when one is given', async () => {
  await openRaise({ [raisePath]: answered(201, fromNoteGeneral) })
  chooseSource('note')
  fillLines()
  expect(record()).toBeDisabled()
  type(/^Review note reference/, 'RN-21')
  expect(record()).toBeEnabled()
  fireEvent.click(record())
  await vi.waitFor(() => {
    expect(posts()).toHaveLength(1)
  })
  expect(sent()[0]?.body).toMatchObject({ raised_from: 'note', note: { note_ref: 'RN-21' } })
  expect(sent()[0]?.body).not.toHaveProperty('source_ref')
  expect((sent()[0]?.body as { note: object }).note).not.toHaveProperty('note_link')
  expect(fromNoteGeneral.current.origin).toEqual({ note_ref: 'RN-21', note_link: null })
})

test('a note with a link sends the link', async () => {
  await openRaise({ [raisePath]: answered(201, fromNote) })
  chooseSource('note')
  fillLines()
  type(/^Review note reference/, 'RN-17')
  type(/^Link to the note/, 'https://review.example.test/notes/RN-17')
  fireEvent.click(record())
  await vi.waitFor(() => {
    expect(posts()).toHaveLength(1)
  })
  expect(sent()[0]?.body).toMatchObject({
    note: { note_ref: 'RN-17', note_link: 'https://review.example.test/notes/RN-17' },
  })
})

test('a manual entry still sends its working paper reference', async () => {
  await openRaise({ [raisePath]: answered(201, fromManual) })
  chooseSource('manual')
  fillLines()
  expect(record()).toBeDisabled()
  type(/^Working paper reference/, 'C-9.1')
  fireEvent.click(record())
  await vi.waitFor(() => {
    expect(posts()).toHaveLength(1)
  })
  expect(sent()[0]?.body).toMatchObject({ raised_from: 'manual', source_ref: 'C-9.1' })
  expect(sent()[0]?.body).not.toHaveProperty('run')
  expect(sent()[0]?.body).not.toHaveProperty('note')
})

test('what was typed for one source is not sent for another', async () => {
  await openRaise({ [raisePath]: answered(201, fromManual) })
  chooseSource('run')
  type(/^Run id/, 'run-7')
  type('Citation 1 source', 'x')
  type('Citation 1 row', '1')
  chooseSource('manual')
  fillLines()
  type(/^Working paper reference/, 'C-9.1')
  fireEvent.click(record())
  await vi.waitFor(() => {
    expect(posts()).toHaveLength(1)
  })
  expect(sent()[0]?.body).not.toHaveProperty('run')
})

test('a refusal is shown in the backend’s words', async () => {
  await openRaise({
    [raisePath]: refusal(refusals.runWithoutDetails.status, refusals.runWithoutDetails.body),
  })
  chooseSource('run')
  fillLines()
  type(/^Run id/, 'run-7')
  type('Citation 1 source', 'sales_register.csv')
  type('Citation 1 row', '1042')
  fireEvent.click(record())
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent('The misstatement was not recorded')
  expect(alert).toHaveTextContent(
    'a misstatement raised from an agent run carries run.run_id and at least one source-row citation',
  )
  expect(alert).toHaveTextContent('answered 422')
})

// ---- the detail ----

function fact(label: string): HTMLElement {
  const term = within(screen.getByRole('region', { name: 'Identification' })).getByText(label, {
    selector: 'dt',
  })
  return term.nextElementSibling as HTMLElement
}

test('a misstatement from an agent run shows the run and its source-row citations', async () => {
  mockApi({ [`GET /api/misstatements/${detailRun.id}`]: detailRun })
  render(<MisstatementPage id={detailRun.id} />)
  await screen.findByRole('heading', { level: 1, name: 'M-2' })
  expect(fact('Raised from')).toHaveTextContent(/^Agent run$/)
  expect(fact('Agent run')).toHaveTextContent(/^run-2026-11-07-0042$/)
  expect(fact('Raised by')).toHaveTextContent(/^workmind@firm$/)
  const citations = within(screen.getByRole('list', { name: 'Source-row citations' })).getAllByRole(
    'listitem',
  )
  expect(citations.map((item) => item.textContent)).toEqual([
    'sales_register.csv, row 1042: Invoice dated 2 April booked in March',
    'sales_register.csv, row 1057',
  ])
  expect(
    within(screen.getByRole('region', { name: 'Identification' })).queryByText(
      'Working paper reference',
    ),
  ).not.toBeInTheDocument()
})

test('a misstatement from a review note shows the note, with its link', async () => {
  mockApi({ [`GET /api/misstatements/${fromNote.id}`]: fromNote })
  render(<MisstatementPage id={fromNote.id} />)
  await screen.findByRole('heading', { level: 1, name: 'M-3' })
  expect(fact('Raised from')).toHaveTextContent(/^Review note$/)
  expect(fact('Review note')).toHaveTextContent('RN-17')
  expect(within(fact('Review note')).getByRole('link')).toHaveAttribute(
    'href',
    'https://review.example.test/notes/RN-17',
  )
})

test('a manual entry shows its working paper reference as such', async () => {
  mockApi({ [`GET /api/misstatements/${fromManual.id}`]: fromManual })
  render(<MisstatementPage id={fromManual.id} />)
  await screen.findByRole('heading', { level: 1, name: 'M-4' })
  expect(fact('Raised from')).toHaveTextContent(/^Manual entry$/)
  expect(fact('Working paper reference (manual entry)')).toHaveTextContent(/^C-9.1$/)
})

// ---- the schedule ----

test('the schedule shows each misstatement’s source and what kind of source it is', async () => {
  mockApi(scheduleAnswers(engagement.id, { engagement, misstatements, evaluation }))
  render(<SchedulePage id={engagement.id} />)
  await screen.findByRole('heading', { level: 1 })
  const table = screen.getByRole('table', { name: 'Schedule of misstatements' })
  expect(within(table).getByRole('columnheader', { name: 'Source' })).toBeInTheDocument()
  const source = (ref: string) =>
    within(within(table).getByRole('row', { name: new RegExp(`^${ref} `) }))
      .getAllByRole('cell')
      .find((cell) => cell.getAttribute('data-label') === 'Source')?.textContent
  expect(source('M-1')).toBe('E-4.2')
  expect(source('M-2')).toBe('run-2026-11-07-0042Agent run')
  expect(source('M-3')).toBe('RN-17Review note')
  expect(source('M-4')).toBe('C-9.1Manual entry')
  // The schedule was captured with one misstatement from each hook.
  expect(misstatements.map((item) => item.current.raised_from)).toEqual([
    'wp',
    'run',
    'note',
    'manual',
  ])
})

// The running totals show the backend's aggregate and add nothing up. The fixtures are the
// backend's real answers (backend/tests/test_frontend_fixtures.py).
import { render, screen, within } from '@testing-library/react'
import { expect, test } from 'vitest'

import { RunningTotals } from '../src/components/RunningTotals'
import { emptyEvaluation, evaluation, spineDownEvaluation } from './scheduleFixtures'

function totalsTable(): HTMLElement {
  return screen.getByRole('table', { name: /Aggregate uncorrected misstatements/ })
}

function cells(rowName: RegExp): (string | null)[] {
  const row = within(totalsTable()).getByRole('row', { name: rowName })
  return within(row)
    .getAllByRole('cell')
    .map((cell) => cell.textContent)
}

test('the four totals are the backend’s figures, in rupees', () => {
  render(<RunningTotals evaluation={evaluation} />)
  // The fixture: five uncorrected items. M-2, the one that increases profit, is below the
  // clearly-trivial threshold and is in none of the totals (spec section 4).
  expect(evaluation.aggregate.not_accumulated).toEqual(['M-2'])
  expect(evaluation.aggregate.profit_before_tax.gross).toBe('195000.00')
  expect(evaluation.aggregate.profit_before_tax.net).toBe('-195000.00')
  expect(cells(/^Profit before tax gross/)[0]).toBe('₹1,95,000.00')
  expect(cells(/^Profit before tax net/)[0]).toBe('-₹1,95,000.00')
  expect(cells(/^Net assets gross/)[0]).toBe('₹1,95,000.00')
  expect(cells(/^Net assets net/)[0]).toBe('-₹1,95,000.00')
})

test('each total is given as a percentage of CTT, PM and OM', () => {
  render(<RunningTotals evaluation={evaluation} />)
  // 1,95,000 against 12,500, 2,50,000 and 4,00,000; 48.75% rounds half up to 48.8%.
  expect(cells(/^Profit before tax gross/).slice(1)).toEqual(['1,560.0%', '78.0%', '48.8%'])
  // A net figure below zero is compared by its size.
  expect(cells(/^Profit before tax net/).slice(1)).toEqual(['1,560.0%', '78.0%', '48.8%'])
  expect(cells(/^Net assets gross/).slice(1)).toEqual(['1,560.0%', '78.0%', '48.8%'])
  expect(cells(/^Net assets net/).slice(1)).toEqual(['1,560.0%', '78.0%', '48.8%'])
})

test('the three lines are named with their amounts and the threshold version', () => {
  render(<RunningTotals evaluation={evaluation} />)
  const headers = within(totalsTable())
    .getAllByRole('columnheader')
    .map((header) => header.textContent)
  expect(headers).toEqual([
    'Effect',
    'Amount',
    '% of CTT₹12,500.00',
    '% of PM₹2,50,000.00',
    '% of OM₹4,00,000.00',
  ])
  expect(screen.getByText('Against thresholds version 1')).toBeInTheDocument()
})

test('it says what was counted, what was not, and that the filters do not change it', () => {
  render(<RunningTotals evaluation={evaluation} />)
  expect(
    screen.getByText(
      '4 misstatements accumulated; clearly trivial, not accumulated: M-2; not counted: M-5 (corrected), M-7 (withdrawn). The filters below do not change these totals.',
    ),
  ).toBeInTheDocument()
  expect(screen.getByText('Classification only, contributing nil: M-6.')).toBeInTheDocument()
})

test('a clearly trivial item is named as not accumulated, and what that means is said', () => {
  render(<RunningTotals evaluation={evaluation} />)
  expect(evaluation.aggregate.counted).not.toContain('M-2')
  expect(
    screen.getByText(
      'A misstatement below the clearly-trivial threshold stays in the schedule and is in none of these totals.',
    ),
  ).toBeInTheDocument()
})

test('what the clearly trivial items come to together is shown, as the backend gives it', () => {
  render(<RunningTotals evaluation={evaluation} />)
  const memo = evaluation.aggregate.not_accumulated_total
  expect([memo.profit_before_tax_gross, memo.net_assets_gross, memo.at_or_above_ctt]).toEqual([
    '8000.00',
    '8000.00',
    false,
  ])
  expect(memo.accumulated_together).toEqual([])
  expect(
    screen.getByText(
      'Together they come to ₹8,000.00 gross on profit before tax and ₹8,000.00 gross on net assets. They stay out while that is below the clearly-trivial threshold on both; once it reaches the threshold on either, all of them are accumulated.',
    ),
  ).toBeInTheDocument()
  // Below the clearly-trivial threshold together: they are left out, and no note is raised.
  expect(screen.queryByRole('note')).not.toBeInTheDocument()
})

test('when the backend has accumulated them together, the screen names them and says why', () => {
  // The backend's answer with its own lists moved the way it moves them (D57): no captured
  // answer reaches this branch. Nothing is added up or decided on the screen.
  const reached = {
    ...evaluation,
    aggregate: {
      ...evaluation.aggregate,
      counted: [...evaluation.aggregate.counted, 'M-2'],
      not_accumulated: [],
      not_accumulated_total: {
        ...evaluation.aggregate.not_accumulated_total,
        profit_before_tax_gross: '12500.00',
        net_assets_gross: '12500.00',
        at_or_above_ctt: true,
        accumulated_together: ['M-2'],
      },
    },
  }
  render(<RunningTotals evaluation={reached} />)
  const note = screen.getByRole('note')
  expect(note).toHaveTextContent('Clearly trivial one by one, accumulated together: M-2.')
  expect(note).toHaveTextContent(
    'Together they come to ₹12,500.00 gross on profit before tax and ₹12,500.00 gross on net assets, which reaches the clearly-trivial threshold (₹12,500.00).',
  )
  expect(note).toHaveTextContent('SA 450 paragraph A2')
  // Nothing is said to be left out any more.
  expect(screen.queryByText(/clearly trivial, not accumulated:/)).not.toBeInTheDocument()
  expect(screen.queryByText(/stays in the schedule and is in none/)).not.toBeInTheDocument()
})

test('with no clearly trivial item nothing is said about one', () => {
  render(<RunningTotals evaluation={emptyEvaluation} />)
  expect(emptyEvaluation.aggregate.not_accumulated).toEqual([])
  expect(screen.queryByText(/clearly trivial, not accumulated:/)).not.toBeInTheDocument()
  expect(screen.queryByText(/below the clearly-trivial threshold/)).not.toBeInTheDocument()
})

test('projected items are never counted without saying so', () => {
  render(<RunningTotals evaluation={evaluation} />)
  expect(
    screen.getByText(
      'Includes projected misstatements (M-4). Without them: profit before tax ₹1,50,000.00 gross and -₹1,50,000.00 net; net assets ₹1,50,000.00 gross and -₹1,50,000.00 net.',
    ),
  ).toBeInTheDocument()
})

test('how the totals are computed is given in the backend’s own words', () => {
  render(<RunningTotals evaluation={evaluation} />)
  expect(screen.getByText('How these totals are computed')).toBeInTheDocument()
  expect(screen.getByText(evaluation.aggregate.basis)).toBeInTheDocument()
})

test('with no thresholds the amounts are shown and no percentage is invented', () => {
  render(<RunningTotals evaluation={emptyEvaluation} />)
  expect(emptyEvaluation.threshold).toBeNull()
  expect(
    screen.getByText('Thresholds are not set, so there are no lines to compare with.'),
  ).toBeInTheDocument()
  expect(cells(/^Profit before tax gross/)).toEqual(['₹0.00', '—', '—', '—'])
  expect(cells(/^Net assets net/)).toEqual(['₹0.00', '—', '—', '—'])
  expect(screen.getByText(/^0 misstatements accumulated\./)).toBeInTheDocument()
  expect(screen.queryByText(/Includes projected/)).not.toBeInTheDocument()
  expect(screen.queryByText(/%$/)).not.toBeInTheDocument()
})

test('totals the backend marks incomplete are flagged, naming what is missing', () => {
  render(<RunningTotals evaluation={spineDownEvaluation} />)
  expect(spineDownEvaluation.aggregate.complete).toBe(false)
  expect(
    screen.getByText(
      'These totals are incomplete: 5 misstatements could not be aggregated (M-1, M-2, M-3, M-4, M-6). The figures cover the others only.',
    ),
  ).toBeInTheDocument()
  expect(screen.getByText(/^0 misstatements accumulated/)).toBeInTheDocument()
})

test('complete totals carry no warning', () => {
  render(<RunningTotals evaluation={evaluation} />)
  expect(screen.queryByText(/These totals are incomplete/)).not.toBeInTheDocument()
})

import { expect, test } from 'vitest'

import {
  NEXT_STATES,
  REASON_REQUIRED,
  STATES,
  determinationLabel,
  exposureStatus,
  gateStatus,
  measureLabel,
  natureLabel,
  recordStatus,
  responseStatus,
  raisedFromLabel,
  sectionLabel,
} from '../src/labels'

test('the moves offered are the ones the specification draws, and no others', () => {
  // Spec section 3.3: raised -> communicated -> corrected | refused | withdrawn.
  expect(NEXT_STATES).toEqual({
    raised: ['communicated'],
    communicated: ['corrected', 'refused', 'withdrawn'],
    corrected: [],
    refused: [],
    withdrawn: [],
  })
  expect(Object.keys(NEXT_STATES).sort()).toEqual([...STATES].sort())
})

test('nothing leads back to raised, and nothing follows a final state', () => {
  const targets = Object.values(NEXT_STATES).flat()
  expect(targets).not.toContain('raised')
  for (const final of ['corrected', 'refused', 'withdrawn'] as const) {
    expect(NEXT_STATES[final]).toEqual([])
  }
})

test('a reason is mandatory for a refusal and a withdrawal only', () => {
  expect([...REASON_REQUIRED].sort()).toEqual(['refused', 'withdrawn'])
})

test('the evaluation’s statuses are worded, and an unknown one is shown as sent and flagged', () => {
  expect(gateStatus('clear')).toEqual({ text: 'Clear', tone: 'good' })
  expect(gateStatus('fires')).toEqual({ text: 'Fires', tone: 'attention' })
  expect(gateStatus('indeterminate').text).toBe('Indeterminate')
  expect(gateStatus('no_thresholds').text).toBe('No thresholds')
  expect(exposureStatus('open')).toEqual({ text: 'Open', tone: 'good' })
  expect(exposureStatus('blocked')).toEqual({ text: 'Blocked', tone: 'attention' })
  expect(exposureStatus('undetermined')).toEqual({ text: 'Undetermined', tone: 'attention' })
  expect(recordStatus('current')).toEqual({ text: 'Current', tone: 'good' })
  expect(recordStatus('stale')).toEqual({ text: 'Stale', tone: 'attention' })
  expect(recordStatus('none').text).toBe('None recorded')
  expect(responseStatus('required')).toEqual({ text: 'Required', tone: 'attention' })
  // A status this screen has never seen is never shown as good news.
  for (const worded of [gateStatus, exposureStatus, recordStatus, responseStatus]) {
    expect(worded('something_new')).toEqual({ text: 'something_new', tone: 'attention' })
  }
  expect(determinationLabel('not_material')).toBe('Not material')
  expect(determinationLabel('material')).toBe('Material')
  expect(determinationLabel('other')).toBe('other')
  expect(determinationLabel(null)).toBeNull()
  expect(measureLabel('profit.gross')).toBe('profit before tax, gross')
  expect(measureLabel('net_assets.net')).toBe('net assets, net')
  expect(measureLabel('something.else')).toBe('something.else')
})

test('a code with no word of its own is shown as the backend sent it', () => {
  expect(raisedFromLabel('wp')).toBe('Working paper')
  expect(raisedFromLabel('manual')).toBe('Manual entry')
  expect(raisedFromLabel('run')).toBe('run')
  expect(natureLabel('PL')).toBe('Profit and loss')
  expect(natureLabel('BS')).toBe('Balance sheet')
  expect(natureLabel('XX')).toBe('XX')
  expect(natureLabel(null)).toBeNull()
  expect(sectionLabel('liabilities')).toBe('Liabilities')
  expect(sectionLabel('something_new')).toBe('something_new')
  expect(sectionLabel(null)).toBeNull()
})

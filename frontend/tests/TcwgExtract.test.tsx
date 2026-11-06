// The TCWG extract (SA 450 paragraph 12; spec section 2 row 12, section 6 item 2;
// acceptance 9; backend D62): the uncorrected misstatements set out for those charged with
// governance, the material ones named individually, the effect on the opinion and the
// request to correct. Every fixture is the backend's real answer
// (backend/tests/test_frontend_fixtures.py): nothing here is hand-written data.
import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import type { TcwgExtract } from '../src/api'
import { TcwgExtractPage } from '../src/pages/TcwgExtractPage'
import notFound from './fixtures/engagement-not-found.json'
import { failApi, mockApi, refusal, requested } from './mockApi'
import { blocked, extractPath, noThresholds, notBlocked, nothing, spineDown } from './tcwgFixtures'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

async function open(extract: TcwgExtract) {
  mockApi({ [extractPath(extract)]: extract })
  const view = render(<TcwgExtractPage id={extract.engagement.id} />)
  await screen.findByRole('heading', { level: 1 })
  return view
}

function panel(name: string): HTMLElement {
  return screen.getByRole('region', { name })
}

function named(): HTMLElement[] {
  return within(
    within(panel('Misstatements named individually')).getByRole('list', {
      name: 'Misstatements named individually',
    }),
  )
    .getAllByRole('heading', { level: 3 })
    .map((heading) => heading.closest('li') as HTMLElement)
}

function cells(table: HTMLElement, row: RegExp): (string | null)[] {
  return within(within(table).getByRole('row', { name: row }))
    .getAllByRole('cell')
    .map((cell) => cell.textContent)
}

// ---- loading and failure ----

test('it says it is loading, asks for the extract once, and names itself', async () => {
  mockApi({ [extractPath(blocked)]: blocked })
  render(<TcwgExtractPage id={blocked.engagement.id} />)
  expect(screen.getByRole('status')).toHaveTextContent('Loading the TCWG extract…')
  expect(
    await screen.findByRole('heading', { level: 1, name: blocked.engagement.label }),
  ).toBeInTheDocument()
  expect(requested()).toEqual([`GET /api/engagements/${blocked.engagement.id}/tcwg-extract`])
  expect(document.title).toBe(`TCWG extract · ${blocked.engagement.label} · Misstatements Rollup`)
  expect(
    screen.getByText(/those charged with governance \(SA 450 paragraph 12\)/),
  ).toBeInTheDocument()
  // Its tab is the one in view.
  const tabs = within(screen.getByRole('navigation', { name: 'Engagement' })).getAllByRole('link')
  expect(
    tabs.filter((tab) => tab.getAttribute('aria-current') === 'page').map((tab) => tab.textContent),
  ).toEqual(['TCWG extract'])
})

test('an engagement that does not exist says so in the backend’s words', async () => {
  const id = '00000000-0000-4000-8000-000000000000'
  mockApi({ [`GET /api/engagements/${id}/tcwg-extract`]: refusal(404, notFound) })
  render(<TcwgExtractPage id={id} />)
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent('This TCWG extract could not be loaded')
  expect(alert).toHaveTextContent(notFound.detail)
  expect(screen.queryByRole('heading', { level: 1 })).not.toBeInTheDocument()
})

test('a backend that cannot be reached is explained, and the extract can be asked for again', async () => {
  failApi()
  render(<TcwgExtractPage id={blocked.engagement.id} />)
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent('The backend could not be reached.')
  mockApi({ [extractPath(blocked)]: blocked })
  fireEvent.click(within(alert).getByRole('button', { name: 'Try again' }))
  expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent(
    blocked.engagement.label,
  )
})

// ---- acceptance 9: every individually material item is named ----

test('acceptance 9: every item the backend names individually is shown by name, with why', async () => {
  await open(blocked)
  const items = named()
  // Exactly the backend's list, in its order: nothing dropped, nothing added.
  expect(items.map((item) => within(item).getByRole('heading', { level: 3 }).textContent)).toEqual(
    blocked.named_individually.map((item) => item.ref),
  )
  expect(blocked.named_individually.map((item) => item.ref)).toEqual(['M-6', 'M-7'])
  expect(panel('Misstatements named individually')).toHaveTextContent(
    '2 uncorrected misstatements named individually',
  )

  // M-6: judgemental, above performance materiality on its own.
  const large = items[0] as HTMLElement
  expect(large).toHaveTextContent('Judgemental')
  expect(large).toHaveTextContent('Individually significant')
  expect(large).toHaveTextContent(
    'Depreciation on plant understated: useful life taken as 15 years',
  )
  expect(large).toHaveTextContent('Named individually because it is')
  expect(large).toHaveTextContent(
    'above performance materiality on its own (individually significant)',
  )
  expect(large).toHaveTextContent('Effect on profit before tax-₹3,00,000.00')
  expect(large).toHaveTextContent('Effect on net assets-₹3,00,000.00')
  // What a judgemental item must say (spec section 3.2), and its Dr/Cr lines.
  expect(large).toHaveTextContent("Auditor's range: ₹2,70,000.00 to ₹3,30,000.00")
  const lines = within(large).getByRole('table', { name: 'Dr/Cr lines of M-6' })
  expect(cells(lines, /^Depreciation /)).toEqual(['₹3,00,000.00', ''])
  expect(cells(lines, /^Accumulated depreciation/)).toEqual(['', '₹3,00,000.00'])
  expect(within(large).getByRole('link', { name: 'M-6' })).toHaveAttribute(
    'href',
    `#/misstatements/${blocked.named_individually[0]?.id ?? ''}`,
  )

  // M-7: below the clearly-trivial threshold, named because it is escalated.
  const escalated = items[1] as HTMLElement
  expect(escalated).toHaveTextContent('Clearly trivial')
  expect(escalated).toHaveTextContent('escalated on a qualitative factor, whatever its amount')
  expect(escalated).toHaveTextContent('Qualitative factors recorded')
  expect(escalated).toHaveTextContent(
    'relates to a related party transaction: Sale to a firm owned by a director; see E-12',
  )
  expect(escalated).toHaveTextContent('Effect on profit before tax-₹3,000.00')
  // The reasons shown are the backend's words.
  for (const item of blocked.named_individually) {
    for (const reason of item.reasons) {
      expect(panel('Misstatements named individually')).toHaveTextContent(reason.text)
    }
  }
})

test('when nothing is above PM or escalated, the extract says none is named', async () => {
  await open(notBlocked)
  expect(panel('Misstatements named individually')).toHaveTextContent(
    'No uncorrected misstatement is above performance materiality or escalated on a qualitative factor, so none is named individually.',
  )
  expect(
    within(panel('Misstatements named individually')).queryByRole('list'),
  ).not.toBeInTheDocument()
  expect(
    screen.queryByRole('region', { name: 'Misstatements that could not be assessed' }),
  ).toBeNull()
})

// ---- the others, summarised and listed ----

test('the other uncorrected misstatements are summarised by type and then listed', async () => {
  await open(blocked)
  const other = panel('Other uncorrected misstatements')
  expect(other).toHaveTextContent('3 other uncorrected misstatements, summarised by type')
  const summary = within(other).getByRole('table', {
    name: 'Other uncorrected misstatements summarised by type',
  })
  expect(cells(summary, /^Factual/)).toEqual([
    '2',
    '₹1,10,000.00',
    '-₹1,10,000.00',
    '₹1,10,000.00',
    '-₹1,10,000.00',
  ])
  expect(cells(summary, /^Judgemental/)).toEqual(['0', '₹0.00', '₹0.00', '₹0.00', '₹0.00'])
  expect(cells(summary, /^Projected/)[0]).toBe('1')
  expect(cells(summary, /^Projected/)[1]).toBe('₹40,000.00')

  const listed = within(other).getByRole('table', {
    name: 'Other uncorrected misstatements listed',
  })
  expect(
    within(listed)
      .getAllByRole('rowheader')
      .map((header) => header.textContent),
  ).toEqual(blocked.other_uncorrected.items.map((item) => item.ref))
  expect(cells(listed, /^M-1 /)).toEqual([
    'Factual',
    'Rent for March not accrued',
    'Raised',
    '-₹60,000.00',
    '-₹60,000.00',
  ])
  // A refused item is still uncorrected, and carries management's reason.
  const refused = within(listed).getByRole('row', { name: /^M-3 / })
  expect(refused).toHaveTextContent('Refused')
  expect(refused).toHaveTextContent(
    "Management's reason for not correcting: Management considers the amount immaterial",
  )
  // No named item is repeated among the others.
  for (const item of blocked.named_individually) {
    expect(within(listed).queryByRole('row', { name: new RegExp(`^${item.ref} `) })).toBeNull()
  }
})

test('the totals show the named, the others and all of them, gross and net', async () => {
  await open(blocked)
  const totals = within(panel('Totals')).getByRole('table', {
    name: /^Totals of the uncorrected misstatements/,
  })
  expect(cells(totals, /^Named individually/)).toEqual([
    '2',
    '₹3,03,000.00',
    '-₹3,03,000.00',
    '₹3,03,000.00',
    '-₹3,03,000.00',
  ])
  expect(cells(totals, /^Other/)).toEqual([
    '3',
    '₹1,50,000.00',
    '-₹1,50,000.00',
    '₹1,50,000.00',
    '-₹1,50,000.00',
  ])
  // The whole is the backend's own aggregate, not a sum made here.
  expect(cells(totals, /^All uncorrected, accumulated/)).toEqual([
    String(blocked.totals.all_uncorrected.count),
    '₹4,53,000.00',
    '-₹4,53,000.00',
    '₹4,53,000.00',
    '-₹4,53,000.00',
  ])
  expect(blocked.totals.all_uncorrected.count).toBe(5)
  expect(panel('Totals')).toHaveTextContent(
    'performance materiality ₹2,50,000.00 · overall materiality ₹4,00,000.00',
  )
  expect(panel('Totals')).toHaveTextContent('₹40,000.00 is projected from samples')
})

test('what is outside the communication is said, with what it comes to', async () => {
  await open(blocked)
  const outside = panel('Not part of this communication')
  expect(outside).toHaveTextContent(
    'Below the clearly-trivial threshold and not accumulated: M-4. Together, gross: profit before tax ₹2,000.00, net assets ₹2,000.00.',
  )
  expect(outside).toHaveTextContent('No longer uncorrected: M-5 (corrected).')
})

test('the prior-period items are shown with both effects, apart from the totals', async () => {
  await open(blocked)
  const prior = panel('Prior-period uncorrected misstatements')
  expect(prior).toHaveTextContent('They are not in the totals above.')
  const items = within(prior).getByRole('table', { name: /^Prior-period items, each with/ })
  expect(cells(items, /^PY-1 /).slice(1)).toEqual([
    '₹0.00',
    '-₹30,000.00',
    '-₹30,000.00',
    '-₹30,000.00',
  ])
  const together = within(prior).getByRole('table', { name: /^The current year's uncorrected/ })
  expect(cells(together, /^Cumulative basis/)).toEqual([
    '₹4,83,000.00',
    '-₹4,83,000.00',
    '₹4,83,000.00',
    '-₹4,83,000.00',
  ])
  expect(cells(together, /^Current-period basis/)[0]).toBe('₹4,53,000.00')
})

test('an extract with no prior-period item shows no prior-period section', async () => {
  await open(notBlocked)
  expect(
    screen.queryByRole('region', { name: 'Prior-period uncorrected misstatements' }),
  ).toBeNull()
})

// ---- the effect on the opinion ----

test('an aggregate at or above overall materiality: an unmodified opinion is blocked', async () => {
  await open(blocked)
  const opinion = panel('Effect on the audit opinion')
  expect(opinion).toHaveTextContent('Unmodified opinion blocked')
  expect(opinion).toHaveTextContent(blocked.opinion_effect.statement)
  expect(opinion).toHaveTextContent(
    'An unmodified opinion cannot be issued on the uncorrected misstatements as they stand.',
  )
  expect(opinion).toHaveTextContent('Blocked by')
  expect(opinion).toHaveTextContent(blocked.opinion_effect.blocked_by[0] ?? 'missing')
  expect(opinion).toHaveTextContent('Overall materiality₹4,00,000.00')
  expect(opinion).toHaveTextContent('Highest aggregate measure₹4,53,000.00')
  expect(opinion).toHaveTextContent("Partner's conclusionNone recorded")
  // The prior-period items are shown with it and are not part of the test.
  expect(opinion).toHaveTextContent('The prior-period items below are shown with it')
  expect(screen.getByText('Ready to communicate')).toBeInTheDocument()
})

test('an aggregate below the lines: an unmodified opinion is not blocked', async () => {
  await open(notBlocked)
  const opinion = panel('Effect on the audit opinion')
  expect(opinion).toHaveTextContent('Unmodified opinion not blocked')
  expect(opinion).toHaveTextContent(
    'The size of the uncorrected misstatements does not block an unmodified opinion.',
  )
  expect(opinion).not.toHaveTextContent('Blocked by')
  expect(opinion).toHaveTextContent('Highest aggregate measure₹1,50,000.00')
})

// ---- the summary and the request ----

test('the summary counts what is communicated and says whether a run records it', async () => {
  await open(blocked)
  const summary = panel('What is communicated')
  expect(summary).toHaveTextContent('Uncorrected misstatements5')
  expect(summary).toHaveTextContent('Named individually2')
  expect(summary).toHaveTextContent('Other3')
  expect(summary).toHaveTextContent('Could not be assessed0')
  expect(summary).toHaveTextContent(
    'Evaluation run:Currentrun 1: the latest run describes the evaluation as it stands',
  )
  expect(summary).toHaveTextContent(blocked.basis)
})

test('the request to correct is the backend’s sentence, set apart', async () => {
  await open(blocked)
  const request = panel('Request to correct')
  expect(within(request).getByText(blocked.request.text).tagName).toBe('BLOCKQUOTE')
  expect(request).toHaveTextContent(
    'We request that the uncorrected misstatements set out in this schedule be corrected.',
  )
  expect(request).toHaveTextContent('SA 450 paragraph 12')
})

test('with nothing uncorrected there is nothing to communicate and nothing to request', async () => {
  await open(nothing)
  expect(panel('What is communicated')).toHaveTextContent('Uncorrected misstatements0')
  expect(panel('Other uncorrected misstatements')).toHaveTextContent(
    'No other uncorrected misstatement is accumulated.',
  )
  const request = panel('Request to correct')
  expect(request).toHaveTextContent(nothing.request.text)
  expect(request).toHaveTextContent('there is nothing to request correction of')
  expect(within(request).queryByText(blocked.request.text)).not.toBeInTheDocument()
  expect(screen.queryByRole('region', { name: 'Not part of this communication' })).toBeNull()
  expect(panel('Effect on the audit opinion')).toHaveTextContent('Unmodified opinion not blocked')
})

// ---- an extract that cannot be relied on says so ----

test('without thresholds the extract is incomplete, and the item is named as not assessed', async () => {
  await open(noThresholds)
  expect(screen.getByText('Incomplete')).toBeInTheDocument()
  expect(screen.queryByText('Ready to communicate')).not.toBeInTheDocument()
  const alert = screen.getByRole('alert')
  expect(alert).toHaveTextContent(
    'This extract is incomplete and is not fit to be communicated as it stands.',
  )
  for (const reason of noThresholds.incomplete_because) expect(alert).toHaveTextContent(reason)

  const unknown = panel('Misstatements that could not be assessed')
  const table = within(unknown).getByRole('table')
  expect(cells(table, /^M-1 /)).toEqual([
    'Rent for the last quarter not accrued',
    'Raised',
    'no thresholds have been set',
  ])
  const opinion = panel('Effect on the audit opinion')
  expect(opinion).toHaveTextContent('Effect undetermined')
  expect(opinion).toHaveTextContent('Undetermined because')
  expect(opinion).toHaveTextContent('no thresholds have been set')
  expect(opinion).toHaveTextContent('Overall materialityNot set')
  expect(panel('Totals')).toHaveTextContent('Thresholds are not set.')
})

test('when the Financial Spine cannot be read, no figure is made up', async () => {
  await open(spineDown)
  expect(screen.getByText('Incomplete')).toBeInTheDocument()
  // The escalated item is still named, on its factor; its effects are said to be unknown.
  const [item] = named()
  expect(item).toHaveTextContent('M-7')
  expect(item).toHaveTextContent('Not banded')
  expect(item).toHaveTextContent('Effect on profit before taxNot determined')
  expect(item).toHaveTextContent('Effect on net assetsNot determined')
  expect(item).toHaveTextContent('Its Dr/Cr lines could not be read from the Financial Spine.')
  expect(item).not.toHaveTextContent('₹')
  // Everything else uncorrected is named as not assessed, never dropped.
  const unknown = within(panel('Misstatements that could not be assessed')).getByRole('table')
  expect(
    within(unknown)
      .getAllByRole('rowheader')
      .map((header) => header.textContent),
  ).toEqual(spineDown.undetermined.map((row) => row.ref))
  expect(spineDown.undetermined).toHaveLength(5)
  expect(panel('Totals')).toHaveTextContent(
    "These totals are short: a misstatement's effects could not be determined.",
  )
  expect(panel('Effect on the audit opinion')).toHaveTextContent('Effect undetermined')
})

// ---- presentation ----

test('the extract can be printed, and the printed page leaves the application off', async () => {
  const print = vi.spyOn(window, 'print').mockImplementation(() => undefined)
  await open(blocked)
  const button = screen.getByRole('button', { name: 'Print or save as PDF' })
  fireEvent.click(button)
  expect(print).toHaveBeenCalledTimes(1)
  // The button, the tabs and the breadcrumb are not part of the printed document.
  expect(button).toHaveClass('print:hidden')
  expect(screen.getByRole('navigation', { name: 'Engagement' }).parentElement).toHaveClass(
    'print:hidden',
  )
  expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toHaveClass('print:hidden')
})

test('the page only reads: nothing is ever sent to the backend', async () => {
  await open(blocked)
  fireEvent.click(screen.getByRole('button', { name: 'Print or save as PDF' }))
  expect(requested().every((request) => request.startsWith('GET'))).toBe(true)
  expect(screen.queryByRole('form')).not.toBeInTheDocument()
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
})

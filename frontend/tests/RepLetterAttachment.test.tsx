// The attachment to the written representation (SA 450 paragraph 14; spec section 2 row
// 14, section 6 item 3; backend D63): the summary of uncorrected misstatements by type, its
// totals gross and net, the prior-period items and the statement management is asked to
// make. Every fixture is the backend's real answer
// (backend/tests/test_frontend_fixtures.py): nothing here is hand-written data.
import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import type { RepLetterAttachment } from '../src/api'
import { RepLetterAttachmentPage } from '../src/pages/RepLetterAttachmentPage'
import notFound from './fixtures/engagement-not-found.json'
import { failApi, mockApi, refusal, requested } from './mockApi'
import {
  attachmentPath,
  noThresholds,
  nothing,
  ready,
  spineDown,
  withCautions,
} from './repLetterFixtures'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const STATEMENT =
  'Management and those charged with governance believe that the effects of the uncorrected misstatements summarised in this schedule are immaterial, individually and in aggregate, to the financial statements as a whole.'

async function open(attachment: RepLetterAttachment) {
  mockApi({ [attachmentPath(attachment)]: attachment })
  const view = render(<RepLetterAttachmentPage id={attachment.engagement.id} />)
  await screen.findByRole('heading', { level: 1 })
  return view
}

function panel(name: string): HTMLElement {
  return screen.getByRole('region', { name })
}

function auditor(): HTMLElement {
  return panel('For the auditor: not part of the attachment')
}

function summary(): HTMLElement {
  return panel('Summary of uncorrected misstatements')
}

function byType(): HTMLElement {
  return within(summary()).getByRole('table', { name: /^Uncorrected misstatements by type/ })
}

function cells(table: HTMLElement, row: RegExp): (string | null)[] {
  return within(within(table).getByRole('row', { name: row }))
    .getAllByRole('cell')
    .map((cell) => cell.textContent)
}

function refsIn(table: HTMLElement): (string | null)[] {
  return within(table)
    .getAllByRole('rowheader')
    .map((header) => header.textContent)
}

// ---- loading and failure ----

test('it says it is loading, asks for the attachment once, and names itself', async () => {
  mockApi({ [attachmentPath(ready)]: ready })
  render(<RepLetterAttachmentPage id={ready.engagement.id} />)
  expect(screen.getByRole('status')).toHaveTextContent('Loading the representation attachment…')
  expect(
    await screen.findByRole('heading', { level: 1, name: ready.engagement.label }),
  ).toBeInTheDocument()
  expect(requested()).toEqual([`GET /api/engagements/${ready.engagement.id}/rep-letter-attachment`])
  expect(document.title).toBe(
    `Representation attachment · ${ready.engagement.label} · Misstatements Rollup`,
  )
  expect(
    screen.getByText(/attachment to the written representation \(SA 450 paragraph 14\)/),
  ).toBeInTheDocument()
  const tabs = within(screen.getByRole('navigation', { name: 'Engagement' })).getAllByRole('link')
  expect(
    tabs.filter((tab) => tab.getAttribute('aria-current') === 'page').map((tab) => tab.textContent),
  ).toEqual(['Representation attachment'])
})

test('an engagement that does not exist says so in the backend’s words', async () => {
  const id = '00000000-0000-4000-8000-000000000000'
  mockApi({ [`GET /api/engagements/${id}/rep-letter-attachment`]: refusal(404, notFound) })
  render(<RepLetterAttachmentPage id={id} />)
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent('This representation attachment could not be loaded')
  expect(alert).toHaveTextContent(notFound.detail)
})

test('a backend that cannot be reached is explained, and the attachment can be asked for again', async () => {
  failApi()
  render(<RepLetterAttachmentPage id={ready.engagement.id} />)
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent('The backend could not be reached.')
  mockApi({ [attachmentPath(ready)]: ready })
  fireEvent.click(within(alert).getByRole('button', { name: 'Try again' }))
  expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent(ready.engagement.label)
})

// ---- the summary ----

test('the summary breaks the misstatements down by type, gross and net, on each measure', async () => {
  await open(ready)
  expect(summary()).toHaveTextContent('4 uncorrected misstatements, by type')
  const table = byType()
  // Number · profit before tax gross, net · net assets gross, net.
  expect(cells(table, /^Factual/)).toEqual([
    '2',
    '₹80,000.00',
    '-₹40,000.00',
    '₹80,000.00',
    '-₹40,000.00',
  ])
  expect(cells(table, /^Judgemental/)).toEqual([
    '1',
    '₹35,000.00',
    '-₹35,000.00',
    '₹35,000.00',
    '-₹35,000.00',
  ])
  expect(cells(table, /^Projected/)).toEqual([
    '1',
    '₹40,000.00',
    '-₹40,000.00',
    '₹40,000.00',
    '-₹40,000.00',
  ])
  // The whole is the backend's own aggregate, shown as sent: not a sum made here.
  expect(cells(table, /^All uncorrected misstatements/)).toEqual([
    String(ready.totals.count),
    '₹1,55,000.00',
    '-₹1,15,000.00',
    '₹1,55,000.00',
    '-₹1,15,000.00',
  ])
  expect(ready.totals.profit_before_tax.gross).toBe('155000.00')
  expect(ready.totals.profit_before_tax.net).toBe('-115000.00')
  expect(
    within(table)
      .getAllByRole('columnheader')
      .map((head) => head.textContent),
  ).toEqual([
    'Type',
    'Number',
    'Profit before tax, gross',
    'Profit before tax, net',
    'Net assets, gross',
    'Net assets, net',
  ])
})

test('every misstatement of the summary is listed under its type, with both effects', async () => {
  await open(ready)
  for (const group of ready.schedule.by_type) {
    const name = `${group.type[0]?.toUpperCase() ?? ''}${group.type.slice(1)} uncorrected misstatements listed`
    const table = within(summary()).getByRole('table', { name })
    // Exactly the backend's rows for that type, in its order.
    expect(refsIn(table)).toEqual(group.items.map((item) => item.ref))
  }
  const factual = within(summary()).getByRole('table', {
    name: 'Factual uncorrected misstatements listed',
  })
  expect(cells(factual, /^M-1 /)).toEqual([
    'Factual',
    'Rent for March not accrued',
    'Communicated',
    '-₹60,000.00',
    '-₹60,000.00',
  ])
  // The reverse of it: gross does not net the two, net does.
  expect(cells(factual, /^M-4 /).slice(3)).toEqual(['₹20,000.00', '₹20,000.00'])
  // A refused item is still uncorrected, and carries management's own reason.
  const judgemental = within(summary()).getByRole('table', {
    name: 'Judgemental uncorrected misstatements listed',
  })
  expect(within(judgemental).getByRole('row', { name: /^M-2 / })).toHaveTextContent(
    "Management's reason for not correcting: Management considers its estimate reasonable",
  )
  expect(summary()).toHaveTextContent(
    'performance materiality ₹2,50,000.00 · overall materiality ₹4,00,000.00',
  )
})

test('a type with no misstatement is in the breakdown at nil and has no list', async () => {
  await open(noThresholds)
  expect(cells(byType(), /^Judgemental/)).toEqual(['0', '₹0.00', '₹0.00', '₹0.00', '₹0.00'])
  expect(
    within(summary()).queryByRole('table', {
      name: 'Judgemental uncorrected misstatements listed',
    }),
  ).toBeNull()
})

// ---- the statement ----

test('the statement is the backend’s sentence, set apart, with where it comes from', async () => {
  await open(ready)
  const statement = panel('Representation')
  expect(within(statement).getByText(STATEMENT).tagName).toBe('BLOCKQUOTE')
  expect(ready.representation.text).toBe(STATEMENT)
  expect(statement).toHaveTextContent('SA 450 paragraph 14')
  expect(statement).toHaveTextContent("It is management's belief, not the auditor's conclusion")
  expect(screen.getByText('Ready to attach')).toBeInTheDocument()
})

test('with nothing accumulated there is no summary and no statement to make', async () => {
  await open(nothing)
  expect(summary()).toHaveTextContent('No uncorrected misstatement is accumulated.')
  expect(within(summary()).queryByRole('table')).not.toBeInTheDocument()
  const statement = panel('Representation')
  expect(statement).toHaveTextContent(nothing.representation.text)
  expect(statement).toHaveTextContent('there is no summary to attach')
  expect(within(statement).queryByText(STATEMENT)).not.toBeInTheDocument()
  expect(auditor()).toHaveTextContent('No caution')
})

// ---- for the auditor ----

test('an evaluation that sits with the statement raises no caution', async () => {
  await open(ready)
  expect(ready.cautions).toEqual([])
  expect(auditor()).toHaveTextContent(
    'No caution: nothing in the evaluation as it stands is at odds with the statement.',
  )
  expect(within(auditor()).queryByRole('list', { name: 'Cautions' })).not.toBeInTheDocument()
  expect(auditor()).toHaveTextContent(
    'Evaluation runCurrentrun 1: the latest run describes the evaluation as it stands',
  )
  expect(auditor()).toHaveTextContent("Partner's conclusionNone recorded")
})

test('every caution of the backend is shown to the auditor, in its words, beside the document', async () => {
  await open(withCautions)
  expect(withCautions.cautions.map((caution) => caution.code)).toEqual([
    'not_communicated',
    'named_individually',
    'opinion_blocked',
  ])
  const shown = within(within(auditor()).getByRole('list', { name: 'Cautions' }))
    .getAllByRole('listitem')
    .map((item) => item.textContent)
  expect(shown).toEqual(withCautions.cautions.map((caution) => caution.text))
  expect(auditor()).toHaveTextContent('3 cautions before this attachment is sent:')
  expect(auditor()).toHaveTextContent('raised and not yet recorded as communicated to management')
  expect(auditor()).toHaveTextContent('named individually in the TCWG extract')
  expect(auditor()).toHaveTextContent('an unmodified opinion is blocked')
  // What is left out of the summary is said here too, with what it comes to.
  expect(auditor()).toHaveTextContent(
    'Below the clearly-trivial threshold and not accumulated: M-4. Together, gross: profit before tax ₹2,000.00, net assets ₹2,000.00.',
  )
  expect(auditor()).toHaveTextContent('No longer uncorrected: M-5 (corrected).')
  // The statement is the same whatever the cautions say: it is management's, not ours.
  expect(within(panel('Representation')).getByText(STATEMENT)).toBeInTheDocument()
  expect(screen.getByText('Ready to attach')).toBeInTheDocument()
  // The cautions are no part of the summary or of the statement.
  for (const caution of withCautions.cautions) {
    expect(summary()).not.toHaveTextContent(caution.text)
    expect(panel('Representation')).not.toHaveTextContent(caution.text)
  }
})

// ---- prior-period items ----

test('prior-period items are shown with both effects, apart from the totals', async () => {
  await open(withCautions)
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
  expect(cells(together, /^Cumulative basis/)[0]).toBe('₹4,83,000.00')
  // The summary's own total is the current year's, unchanged by them.
  expect(cells(byType(), /^All uncorrected misstatements/)[1]).toBe('₹4,53,000.00')
})

test('an attachment with no prior-period item shows no prior-period section', async () => {
  await open(ready)
  expect(
    screen.queryByRole('region', { name: 'Prior-period uncorrected misstatements' }),
  ).toBeNull()
})

// ---- an attachment that cannot be relied on says so ----

test('without thresholds the attachment is incomplete and says why', async () => {
  await open(noThresholds)
  expect(screen.getByText('Incomplete')).toBeInTheDocument()
  expect(screen.queryByText('Ready to attach')).not.toBeInTheDocument()
  const alert = screen.getByRole('alert')
  expect(alert).toHaveTextContent(
    'This attachment is incomplete and is not fit to be sent as it stands.',
  )
  for (const reason of noThresholds.incomplete_because) expect(alert).toHaveTextContent(reason)
  // The item and its effects are still shown: only the evaluation cannot be made.
  expect(cells(byType(), /^Factual/)[1]).toBe('₹3,00,000.00')
})

test('when the Financial Spine cannot be read, the items are named and no figure is made up', async () => {
  await open(spineDown)
  expect(screen.getByText('Incomplete')).toBeInTheDocument()
  const unknown = within(summary()).getByRole('table', {
    name: 'Uncorrected misstatements whose effects could not be determined',
  })
  expect(refsIn(unknown)).toEqual(spineDown.schedule.undetermined.map((row) => row.ref))
  expect(spineDown.schedule.undetermined).toHaveLength(6)
  expect(cells(unknown, /^M-1 /).slice(3)).toEqual(['Not determined', 'Not determined'])
  expect(unknown).not.toHaveTextContent('₹')
  expect(summary()).toHaveTextContent(
    "These totals are short: a misstatement's effects could not be determined.",
  )
  // No list by type: nothing has a known effect.
  expect(
    within(summary()).queryByRole('table', { name: 'Factual uncorrected misstatements listed' }),
  ).toBeNull()
})

// ---- presentation ----

test('the printed page is the attachment alone', async () => {
  const print = vi.spyOn(window, 'print').mockImplementation(() => undefined)
  await open(withCautions)
  const button = screen.getByRole('button', { name: 'Print or save as PDF' })
  fireEvent.click(button)
  expect(print).toHaveBeenCalledTimes(1)
  // Left off the printed page: the button, the tabs, the breadcrumb, the status, and
  // everything that is for the auditor.
  expect(button).toHaveClass('print:hidden')
  expect(screen.getByRole('navigation', { name: 'Engagement' }).parentElement).toHaveClass(
    'print:hidden',
  )
  expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toHaveClass('print:hidden')
  expect(screen.getByText('Ready to attach').parentElement).toHaveClass('print:hidden')
  expect(auditor().parentElement).toHaveClass('print:hidden')
  // On it: the summary, the prior-period items and the statement.
  for (const name of [
    'Summary of uncorrected misstatements',
    'Prior-period uncorrected misstatements',
    'Representation',
  ]) {
    expect(panel(name).closest('.print\\:hidden')).toBeNull()
  }
})

test('the page only reads: nothing is ever sent to the backend', async () => {
  await open(ready)
  expect(requested().every((request) => request.startsWith('GET'))).toBe(true)
  expect(screen.queryByRole('form')).not.toBeInTheDocument()
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
})
